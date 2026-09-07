"""Chronological ML meta-filter for Ariatrading research.

The model is deliberately downstream of the deterministic setup engine. It can
score an already-valid LONG/SHORT signal, but it cannot create a new direction.
Training uses chronological data only; no shuffling is permitted.
"""

from dataclasses import dataclass

from .ml_features import FEATURE_NAMES, MLSample


@dataclass(frozen=True)
class MLResearchMetrics:
    train_samples: int
    test_samples: int
    accuracy: float
    positive_precision: float
    positive_recall: float


@dataclass(frozen=True)
class MetaFilterResult:
    metrics: MLResearchMetrics
    test_scores: tuple[float, ...]
    test_labels: tuple[int, ...]


class MetaFilterModel:
    """Small, deterministic gradient-boosted classifier for signal quality research."""

    def __init__(
        self,
        *,
        learning_rate: float = 0.05,
        max_iter: int = 100,
        max_leaf_nodes: int = 15,
        min_samples_leaf: int = 10,
        l2_regularization: float = 0.1,
        random_state: int = 42,
    ) -> None:
        try:
            from sklearn.ensemble import HistGradientBoostingClassifier
        except ImportError as exc:
            raise RuntimeError(
                "scikit-learn is required for MetaFilterModel; install the ML requirements"
            ) from exc

        if not 0 < learning_rate <= 1:
            raise ValueError("learning_rate must be in (0, 1]")
        if max_iter < 1 or max_leaf_nodes < 2 or min_samples_leaf < 1:
            raise ValueError("invalid model tree configuration")
        if l2_regularization < 0:
            raise ValueError("l2_regularization must be >= 0")

        self._model = HistGradientBoostingClassifier(
            learning_rate=learning_rate,
            max_iter=max_iter,
            max_leaf_nodes=max_leaf_nodes,
            min_samples_leaf=min_samples_leaf,
            l2_regularization=l2_regularization,
            early_stopping=False,
            random_state=random_state,
        )
        self.feature_names = FEATURE_NAMES
        self._fitted = False

    def fit(self, samples: list[MLSample] | tuple[MLSample, ...]) -> None:
        """Fit on chronological samples. Caller controls the train/test boundary."""
        sample = tuple(samples)
        if not sample:
            raise ValueError("samples must not be empty")
        labels = [item.label for item in sample]
        if set(labels) != {0, 1}:
            raise ValueError("training samples must contain both label classes")
        X = [item.features for item in sample]
        self._model.fit(X, labels)
        self._fitted = True

    def score(self, features: tuple[float, ...] | list[float]) -> float:
        """Return the model's class-1 score; it is not a calibrated win probability."""
        if not self._fitted:
            raise RuntimeError("model must be fitted before scoring")
        if len(features) != len(FEATURE_NAMES):
            raise ValueError("feature vector has incorrect length")
        return float(self._model.predict_proba([features])[0][1])

    def approve(self, features: tuple[float, ...] | list[float], threshold: float = 0.55) -> bool:
        """Return whether the model score clears the research threshold."""
        if not 0 < threshold < 1:
            raise ValueError("threshold must be between 0 and 1")
        return self.score(features) >= threshold


def chronological_train_test(
    samples: list[MLSample] | tuple[MLSample, ...],
    *,
    train_ratio: float = 0.70,
    model: MetaFilterModel | None = None,
) -> MetaFilterResult:
    """Fit on the oldest samples and evaluate only on later samples."""
    if not 0 < train_ratio < 1:
        raise ValueError("train_ratio must be between 0 and 1")
    sample = tuple(samples)
    split = int(len(sample) * train_ratio)
    if split < 2 or len(sample) - split < 1:
        raise ValueError("not enough samples for chronological train/test split")
    train = sample[:split]
    test = sample[split:]
    learner = model or MetaFilterModel()
    learner.fit(train)

    scores = tuple(learner.score(item.features) for item in test)
    predictions = tuple(int(score >= 0.5) for score in scores)
    labels = tuple(item.label for item in test)
    correct = sum(prediction == label for prediction, label in zip(predictions, labels))
    true_positive = sum(prediction == label == 1 for prediction, label in zip(predictions, labels))
    predicted_positive = sum(prediction == 1 for prediction in predictions)
    actual_positive = sum(label == 1 for label in labels)
    metrics = MLResearchMetrics(
        train_samples=len(train),
        test_samples=len(test),
        accuracy=correct / len(test),
        positive_precision=true_positive / predicted_positive if predicted_positive else 0.0,
        positive_recall=true_positive / actual_positive if actual_positive else 0.0,
    )
    return MetaFilterResult(metrics=metrics, test_scores=scores, test_labels=labels)


__all__ = ["MLResearchMetrics", "MetaFilterModel", "MetaFilterResult", "chronological_train_test"]
