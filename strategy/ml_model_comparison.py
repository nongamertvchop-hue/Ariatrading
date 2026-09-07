"""Research-only comparison of the baseline ML model and deep challengers.

The deterministic two-setup engine remains the only source of direction. This
module compares model quality on one identical chronological train/test window;
it never chooses a winner, changes a threshold, or changes strategy behavior.

The decision boundary is fixed at 0.5 for descriptive classification metrics.
It is intentionally not optimized on the OOS set.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import mean, pstdev

from .deep_learning import DeepLearningMetrics, ModelType, train_deep_sequence_model
from .ml_features import MLSample
from .ml_meta import MetaFilterModel


@dataclass(frozen=True)
class ModelClassificationMetrics:
    """Descriptive classification metrics for one fixed evaluation window."""

    model_name: str
    train_samples: int
    test_samples: int
    accuracy: float
    positive_precision: float
    positive_recall: float

    @property
    def valid(self) -> bool:
        return (
            self.train_samples > 0
            and self.test_samples > 0
            and all(
                isfinite(float(value))
                for value in (self.accuracy, self.positive_precision, self.positive_recall)
            )
            and all(0.0 <= float(value) <= 1.0 for value in (self.accuracy, self.positive_precision, self.positive_recall))
        )


@dataclass(frozen=True)
class MLModelComparison:
    """Side-by-side evidence; no automatic model selection is performed."""

    baseline: ModelClassificationMetrics
    lstm: ModelClassificationMetrics
    transformer: ModelClassificationMetrics

    @property
    def accuracy_delta_lstm_vs_baseline(self) -> float:
        return self.lstm.accuracy - self.baseline.accuracy

    @property
    def accuracy_delta_transformer_vs_baseline(self) -> float:
        return self.transformer.accuracy - self.baseline.accuracy

    @property
    def positive_precision_delta_lstm_vs_baseline(self) -> float:
        return self.lstm.positive_precision - self.baseline.positive_precision

    @property
    def positive_precision_delta_transformer_vs_baseline(self) -> float:
        return self.transformer.positive_precision - self.baseline.positive_precision


@dataclass(frozen=True)
class MLChallengerAggregate:
    """Across-window descriptive summary for a single model."""

    model_name: str
    windows: int
    accuracies: tuple[float, ...]
    positive_precisions: tuple[float, ...]
    positive_recalls: tuple[float, ...]

    @property
    def mean_accuracy(self) -> float:
        return mean(self.accuracies)

    @property
    def std_accuracy(self) -> float:
        return pstdev(self.accuracies) if len(self.accuracies) > 1 else 0.0

    @property
    def mean_positive_precision(self) -> float:
        return mean(self.positive_precisions)

    @property
    def mean_positive_recall(self) -> float:
        return mean(self.positive_recalls)


def _validate_samples(train_samples, test_samples) -> tuple[tuple[MLSample, ...], tuple[MLSample, ...]]:
    train = tuple(train_samples)
    test = tuple(test_samples)
    if not train or not test:
        raise ValueError("train_samples and test_samples must not be empty")

    width = len(train[0].features)
    if width == 0:
        raise ValueError("features must not be empty")
    previous = None
    for sample in train:
        if len(sample.features) != width or sample.label not in (0, 1):
            raise ValueError("invalid training sample")
        if previous is not None and sample.index <= previous:
            raise ValueError("train_samples must be strictly chronological")
        if any(not isfinite(float(value)) for value in sample.features):
            raise ValueError("features must be finite")
        previous = sample.index
    if len({sample.label for sample in train}) != 2:
        raise ValueError("training samples must contain both label classes")

    previous = None
    for sample in test:
        if len(sample.features) != width or sample.label not in (0, 1):
            raise ValueError("invalid test sample")
        if previous is not None and sample.index <= previous:
            raise ValueError("test_samples must be strictly chronological")
        if any(not isfinite(float(value)) for value in sample.features):
            raise ValueError("features must be finite")
        previous = sample.index
    if train[-1].index >= test[0].index:
        raise ValueError("train_samples must strictly precede test_samples")
    return train, test


def _classification_metrics(model_name: str, train_count: int, labels: tuple[int, ...], scores: tuple[float, ...]) -> ModelClassificationMetrics:
    if not labels or len(labels) != len(scores):
        raise ValueError("labels and scores must have equal non-zero length")
    if any(not isfinite(float(score)) or not 0.0 <= float(score) <= 1.0 for score in scores):
        raise ValueError("model scores must be finite and between 0 and 1")
    predictions = tuple(int(score >= 0.5) for score in scores)
    correct = sum(prediction == label for prediction, label in zip(predictions, labels))
    true_positive = sum(prediction == label == 1 for prediction, label in zip(predictions, labels))
    predicted_positive = sum(prediction == 1 for prediction in predictions)
    actual_positive = sum(label == 1 for label in labels)
    return ModelClassificationMetrics(
        model_name=model_name,
        train_samples=train_count,
        test_samples=len(labels),
        accuracy=correct / len(labels),
        positive_precision=true_positive / predicted_positive if predicted_positive else 0.0,
        positive_recall=true_positive / actual_positive if actual_positive else 0.0,
    )


def compare_ml_models(
    train_samples: list[MLSample] | tuple[MLSample, ...],
    test_samples: list[MLSample] | tuple[MLSample, ...],
    *,
    sequence_length: int = 8,
    hidden_size: int = 32,
    layers: int = 1,
    heads: int = 4,
    epochs: int = 20,
    learning_rate: float = 1e-3,
    seed: int = 42,
) -> MLModelComparison:
    """Compare HGB, LSTM, and Transformer on exactly the same OOS samples.

    This is intentionally a single fixed-window evaluator. For walk-forward
    research, call it independently for every OOS fold and aggregate the
    resulting metrics without selecting a model from those same OOS results.
    """
    train, test = _validate_samples(train_samples, test_samples)

    baseline_model = MetaFilterModel()
    baseline_model.fit(train)
    baseline_scores = tuple(baseline_model.score(sample.features) for sample in test)
    baseline = _classification_metrics("hist_gradient_boosting", len(train), tuple(sample.label for sample in test), baseline_scores)

    common = {
        "train_samples": train,
        "test_samples": test,
        "sequence_length": sequence_length,
        "hidden_size": hidden_size,
        "layers": layers,
        "heads": heads,
        "epochs": epochs,
        "learning_rate": learning_rate,
        "seed": seed,
    }
    _, lstm_metrics = train_deep_sequence_model(model_type="lstm", **common)
    _, transformer_metrics = train_deep_sequence_model(model_type="transformer", **common)

    if not isinstance(lstm_metrics, DeepLearningMetrics) or not isinstance(transformer_metrics, DeepLearningMetrics):
        raise TypeError("deep-learning trainer returned invalid metrics")
    if not lstm_metrics.valid or not transformer_metrics.valid:
        raise ValueError("deep-learning metrics are invalid")

    # The deep trainer evaluates the same test_samples and fixed 0.5 boundary.
    lstm = ModelClassificationMetrics(
        model_name="lstm",
        train_samples=len(train),
        test_samples=lstm_metrics.test_samples,
        accuracy=lstm_metrics.accuracy,
        positive_precision=lstm_metrics.positive_precision,
        positive_recall=lstm_metrics.positive_recall,
    )
    transformer = ModelClassificationMetrics(
        model_name="transformer",
        train_samples=len(train),
        test_samples=transformer_metrics.test_samples,
        accuracy=transformer_metrics.accuracy,
        positive_precision=transformer_metrics.positive_precision,
        positive_recall=transformer_metrics.positive_recall,
    )
    return MLModelComparison(baseline=baseline, lstm=lstm, transformer=transformer)


def aggregate_challenger_results(comparisons: list[MLModelComparison] | tuple[MLModelComparison, ...]) -> tuple[MLChallengerAggregate, ...]:
    """Aggregate fixed-window results without ranking or selecting a winner."""
    items = tuple(comparisons)
    if not items:
        raise ValueError("comparisons must not be empty")
    return tuple(
        MLChallengerAggregate(
            model_name=model_name,
            windows=len(items),
            accuracies=tuple(getattr(item, model_name).accuracy for item in items),
            positive_precisions=tuple(getattr(item, model_name).positive_precision for item in items),
            positive_recalls=tuple(getattr(item, model_name).positive_recall for item in items),
        )
        for model_name in ("baseline", "lstm", "transformer")
    )


__all__ = [
    "ModelClassificationMetrics",
    "MLModelComparison",
    "MLChallengerAggregate",
    "compare_ml_models",
    "aggregate_challenger_results",
]
