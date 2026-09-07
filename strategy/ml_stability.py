"""Leakage-safe diagnostics for ML meta-filter feature stability.

This module is a research diagnostic only. It does not generate trade signals,
change thresholds, or select an execution configuration. Permutation importance
is computed from a fitted model and samples supplied by the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Protocol, Sequence

from .ml_features import MLSample


class ScoreModel(Protocol):
    """Minimal public interface required by the stability diagnostic."""

    def score(self, features: Sequence[float]) -> float:
        ...


@dataclass(frozen=True)
class FeatureImportance:
    """Permutation-importance summary for one feature."""

    feature_index: int
    mean_accuracy_drop: float
    std_accuracy_drop: float
    repeats: int


@dataclass(frozen=True)
class MLStabilityReport:
    """Deterministic permutation-importance report."""

    sample_count: int
    feature_count: int
    baseline_accuracy: float
    importance: tuple[FeatureImportance, ...]


def _validate_samples(samples: Sequence[MLSample]) -> int:
    if not samples:
        raise ValueError("samples must not be empty")
    feature_count = len(samples[0].features)
    if feature_count == 0:
        raise ValueError("samples must contain at least one feature")
    for sample in samples:
        if len(sample.features) != feature_count:
            raise ValueError("all samples must have the same feature count")
        if sample.label not in (0, 1):
            raise ValueError("sample labels must be 0 or 1")
        if any(not math.isfinite(value) for value in sample.features):
            raise ValueError("sample features must be finite")
    return feature_count


def _accuracy(model: ScoreModel, samples: Sequence[MLSample]) -> float:
    correct = 0
    for sample in samples:
        score = model.score(sample.features)
        if not math.isfinite(score):
            raise ValueError("model score must be finite")
        prediction = 1 if score >= 0.5 else 0
        correct += prediction == sample.label
    return correct / len(samples)


def permutation_feature_importance(
    model: ScoreModel,
    samples: Sequence[MLSample],
    *,
    repeats: int = 5,
    seed: int = 42,
) -> MLStabilityReport:
    """Measure accuracy degradation after deterministic feature permutation.

    The samples must represent a single evaluation set. For honest OOS
    research, call this only on a fold that was not used to fit ``model``.
    Results are diagnostic and must not be used to tune the same OOS fold.
    """
    if repeats < 1:
        raise ValueError("repeats must be >= 1")
    if not isinstance(seed, int):
        raise TypeError("seed must be an int")
    feature_count = _validate_samples(samples)
    baseline = _accuracy(model, samples)
    mutable = [list(sample.features) for sample in samples]
    labels = [sample.label for sample in samples]
    importance: list[FeatureImportance] = []

    for feature_index in range(feature_count):
        drops: list[float] = []
        original = [row[feature_index] for row in mutable]
        for repeat in range(repeats):
            permutation = list(original)
            random.Random(seed + feature_index * 1_000_003 + repeat).shuffle(permutation)
            permuted_samples = []
            for row_index, row in enumerate(mutable):
                features = list(row)
                features[feature_index] = permutation[row_index]
                permuted_samples.append(MLSample(tuple(features), labels[row_index]))
            permuted_accuracy = _accuracy(model, permuted_samples)
            drops.append(baseline - permuted_accuracy)
        mean = sum(drops) / len(drops)
        variance = sum((value - mean) ** 2 for value in drops) / len(drops)
        importance.append(
            FeatureImportance(
                feature_index=feature_index,
                mean_accuracy_drop=mean,
                std_accuracy_drop=math.sqrt(variance),
                repeats=repeats,
            )
        )

    importance.sort(key=lambda item: (-item.mean_accuracy_drop, item.feature_index))
    return MLStabilityReport(
        sample_count=len(samples),
        feature_count=feature_count,
        baseline_accuracy=baseline,
        importance=tuple(importance),
    )


__all__ = ["FeatureImportance", "MLStabilityReport", "permutation_feature_importance"]
