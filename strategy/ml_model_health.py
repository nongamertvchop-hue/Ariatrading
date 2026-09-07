"""Research-only ML performance and calibration diagnostics.

The deterministic two-setup strategy remains the source of direction. This
module evaluates an already-trained ML meta-filter on chronological samples;
it never selects thresholds, retrains the model, or changes trading behavior.
"""

from dataclasses import dataclass
from math import isfinite
from typing import Protocol

from .ml_features import MLSample


class ScoreModel(Protocol):
    """Minimal interface required from an already-fitted ML model."""

    def score(self, features: tuple[float, ...] | list[float]) -> float:
        ...


@dataclass(frozen=True)
class CalibrationBin:
    """Score-bin calibration statistics."""

    lower: float
    upper: float
    samples: int
    mean_score: float
    observed_positive_rate: float


@dataclass(frozen=True)
class MLModelHealth:
    """Performance and score-distribution diagnostics for one sample set."""

    samples: int
    accuracy: float
    positive_precision: float
    positive_recall: float
    brier_score: float
    score_mean: float
    score_std: float
    positive_prediction_rate: float
    calibration_error: float
    calibration_bins: tuple[CalibrationBin, ...]


@dataclass(frozen=True)
class MLModelHealthReport:
    """Train/test health comparison for an already-trained ML model."""

    train: MLModelHealth
    test: MLModelHealth
    accuracy_delta: float
    positive_precision_delta: float
    positive_recall_delta: float
    brier_score_delta: float
    score_mean_delta: float
    score_std_delta: float
    positive_prediction_rate_delta: float
    calibration_error_delta: float


def _validate_samples(samples: tuple[MLSample, ...] | list[MLSample], name: str) -> int:
    if not samples:
        raise ValueError(f"{name} must not be empty")
    width = len(samples[0].features)
    if width == 0:
        raise ValueError("features must not be empty")
    for sample in samples:
        if sample.label not in {0, 1}:
            raise ValueError("labels must be 0 or 1")
        if len(sample.features) != width:
            raise ValueError("all samples must have the same feature width")
        if not all(isfinite(float(value)) for value in sample.features):
            raise ValueError("features must be finite")
    return width


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _std(values: list[float], mean: float) -> float:
    return (sum((value - mean) ** 2 for value in values) / len(values)) ** 0.5


def _score(model: ScoreModel, sample: MLSample) -> float:
    value = float(model.score(sample.features))
    if not isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError("model scores must be finite and between 0 and 1")
    return value


def _calibration_bins(scores: list[float], labels: list[int], bins: int) -> tuple[CalibrationBin, ...]:
    result: list[CalibrationBin] = []
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        selected = [i for i, score in enumerate(scores) if (lower <= score < upper) or (index == bins - 1 and score == upper)]
        if not selected:
            continue
        mean_score = _mean([scores[i] for i in selected])
        observed = _mean([float(labels[i]) for i in selected])
        result.append(CalibrationBin(lower, upper, len(selected), mean_score, observed))
    return tuple(result)


def _health(model: ScoreModel, samples: tuple[MLSample, ...], bins: int) -> MLModelHealth:
    scores = [_score(model, sample) for sample in samples]
    labels = [sample.label for sample in samples]
    predictions = [int(score >= 0.5) for score in scores]
    correct = sum(prediction == label for prediction, label in zip(predictions, labels))
    true_positive = sum(prediction == label == 1 for prediction, label in zip(predictions, labels))
    predicted_positive = sum(prediction == 1 for prediction in predictions)
    actual_positive = sum(label == 1 for label in labels)
    brier = _mean([(score - label) ** 2 for score, label in zip(scores, labels)])
    mean_score = _mean(scores)
    calibration_bins = _calibration_bins(scores, labels, bins)
    calibration_error = sum(
        item.samples / len(samples) * abs(item.mean_score - item.observed_positive_rate)
        for item in calibration_bins
    )
    return MLModelHealth(
        samples=len(samples),
        accuracy=correct / len(samples),
        positive_precision=true_positive / predicted_positive if predicted_positive else 0.0,
        positive_recall=true_positive / actual_positive if actual_positive else 0.0,
        brier_score=brier,
        score_mean=mean_score,
        score_std=_std(scores, mean_score),
        positive_prediction_rate=predicted_positive / len(samples),
        calibration_error=calibration_error,
        calibration_bins=calibration_bins,
    )


def analyze_model_health(
    model: ScoreModel,
    train_samples: tuple[MLSample, ...] | list[MLSample],
    test_samples: tuple[MLSample, ...] | list[MLSample],
    *,
    bins: int = 10,
) -> MLModelHealthReport:
    """Compare an already-trained model on chronological train/test samples.

    The model is never fitted here. A fixed 0.5 boundary is used only for
    descriptive classification metrics. Calibration statistics describe the
    model score; they must not be interpreted as a calibrated win probability
    until independently calibrated and validated out of sample.
    """
    train = tuple(train_samples)
    test = tuple(test_samples)
    train_width = _validate_samples(train, "train_samples")
    test_width = _validate_samples(test, "test_samples")
    if train_width != test_width:
        raise ValueError("train and test feature widths must match")
    if bins < 2 or bins > 100:
        raise ValueError("bins must be between 2 and 100")

    train_health = _health(model, train, bins)
    test_health = _health(model, test, bins)
    return MLModelHealthReport(
        train=train_health,
        test=test_health,
        accuracy_delta=test_health.accuracy - train_health.accuracy,
        positive_precision_delta=test_health.positive_precision - train_health.positive_precision,
        positive_recall_delta=test_health.positive_recall - train_health.positive_recall,
        brier_score_delta=test_health.brier_score - train_health.brier_score,
        score_mean_delta=test_health.score_mean - train_health.score_mean,
        score_std_delta=test_health.score_std - train_health.score_std,
        positive_prediction_rate_delta=test_health.positive_prediction_rate - train_health.positive_prediction_rate,
        calibration_error_delta=test_health.calibration_error - train_health.calibration_error,
    )


__all__ = ["CalibrationBin", "MLModelHealth", "MLModelHealthReport", "analyze_model_health"]
