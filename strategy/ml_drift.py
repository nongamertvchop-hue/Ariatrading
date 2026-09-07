"""Research-only diagnostics for ML feature distribution drift.

Training samples define the bin boundaries; test samples are never used to
choose those boundaries. The module reports drift metrics only and does not
change signals, thresholds, or execution behavior.
"""

from dataclasses import dataclass
from math import isfinite

from .ml_features import MLSample


@dataclass(frozen=True)
class FeatureDrift:
    """Distribution-drift diagnostics for one feature."""

    feature_index: int
    train_mean: float
    test_mean: float
    train_std: float
    test_std: float
    mean_shift_std: float
    psi: float


@dataclass(frozen=True)
class MLDriftReport:
    """Aggregate feature-drift report for one chronological train/test split."""

    train_sample_count: int
    test_sample_count: int
    feature_count: int
    features: tuple[FeatureDrift, ...]


def _validate_samples(samples: tuple[MLSample, ...] | list[MLSample], name: str) -> int:
    if not samples:
        raise ValueError(f"{name} must not be empty")
    width = len(samples[0].features)
    if width == 0:
        raise ValueError("features must not be empty")
    for sample in samples:
        if len(sample.features) != width:
            raise ValueError("all samples must have the same feature width")
        for value in sample.features:
            if not isfinite(float(value)):
                raise ValueError("features must be finite")
    return width


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _std(values: list[float], mean: float) -> float:
    return (sum((value - mean) ** 2 for value in values) / len(values)) ** 0.5


def _psi(train: list[float], test: list[float], bins: int, epsilon: float) -> float:
    low = min(train)
    high = max(train)
    if low == high:
        return 0.0 if all(value == low for value in test) else float("inf")

    width = (high - low) / bins
    expected = [0] * bins
    actual = [0] * bins
    for value in train:
        bucket = min(bins - 1, int((value - low) / width))
        expected[bucket] += 1
    for value in test:
        bucket = min(bins - 1, max(0, int((value - low) / width)))
        actual[bucket] += 1

    train_total = float(len(train))
    test_total = float(len(test))
    total = 0.0
    for expected_count, actual_count in zip(expected, actual):
        expected_pct = max(expected_count / train_total, epsilon)
        actual_pct = max(actual_count / test_total, epsilon)
        total += (actual_pct - expected_pct) * __import__("math").log(actual_pct / expected_pct)
    return total


def analyze_feature_drift(
    train_samples: tuple[MLSample, ...] | list[MLSample],
    test_samples: tuple[MLSample, ...] | list[MLSample],
    *,
    bins: int = 10,
    epsilon: float = 1e-6,
) -> MLDriftReport:
    """Measure feature drift using training-only bin boundaries.

    ``psi`` is a diagnostic statistic, not a probability and not a trading
    quality score. No threshold is applied here because threshold selection
    belongs to a separately controlled research decision.
    """
    train_width = _validate_samples(train_samples, "train_samples")
    test_width = _validate_samples(test_samples, "test_samples")
    if train_width != test_width:
        raise ValueError("train and test feature widths must match")
    if bins < 2:
        raise ValueError("bins must be >= 2")
    if not 0 < epsilon < 1:
        raise ValueError("epsilon must be between 0 and 1")

    diagnostics: list[FeatureDrift] = []
    for feature_index in range(train_width):
        train = [float(sample.features[feature_index]) for sample in train_samples]
        test = [float(sample.features[feature_index]) for sample in test_samples]
        train_mean = _mean(train)
        test_mean = _mean(test)
        train_std = _std(train, train_mean)
        test_std = _std(test, test_mean)
        mean_shift_std = (test_mean - train_mean) / train_std if train_std else (0.0 if test_mean == train_mean else float("inf"))
        diagnostics.append(
            FeatureDrift(
                feature_index=feature_index,
                train_mean=train_mean,
                test_mean=test_mean,
                train_std=train_std,
                test_std=test_std,
                mean_shift_std=mean_shift_std,
                psi=_psi(train, test, bins, epsilon),
            )
        )

    return MLDriftReport(
        train_sample_count=len(train_samples),
        test_sample_count=len(test_samples),
        feature_count=train_width,
        features=tuple(diagnostics),
    )


__all__ = ["FeatureDrift", "MLDriftReport", "analyze_feature_drift"]
