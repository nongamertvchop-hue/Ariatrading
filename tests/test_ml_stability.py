from dataclasses import dataclass

import pytest

from strategy.ml_features import MLSample
from strategy.ml_stability import permutation_feature_importance


@dataclass
class ToyModel:
    def score(self, features):
        return 1.0 if features[0] > 0 else 0.0


def make_samples():
    return [
        MLSample(i, None, (1.0, float(i)), 1) for i in range(5)
    ] + [
        MLSample(i + 5, None, (-1.0, float(i)), 0) for i in range(5)
    ]


def test_permutation_importance_is_deterministic_and_sorted():
    samples = make_samples()
    first = permutation_feature_importance(ToyModel(), samples, repeats=4, seed=7)
    second = permutation_feature_importance(ToyModel(), samples, repeats=4, seed=7)

    assert first == second
    assert first.sample_count == 10
    assert first.feature_count == 2
    assert first.baseline_accuracy == 1.0
    assert first.importance[0].feature_index == 0
    assert first.importance[0].mean_accuracy_drop > 0.0
    assert all(item.repeats == 4 for item in first.importance)


def test_stability_rejects_inconsistent_feature_width():
    samples = make_samples()
    samples.append(MLSample(99, None, (1.0,), 1))
    with pytest.raises(ValueError, match="same feature count"):
        permutation_feature_importance(ToyModel(), samples)


def test_stability_rejects_invalid_repeats_and_labels():
    with pytest.raises(ValueError, match="repeats"):
        permutation_feature_importance(ToyModel(), make_samples(), repeats=0)

    bad = make_samples()
    bad[0] = MLSample(0, None, bad[0].features, 2)
    with pytest.raises(ValueError, match="labels"):
        permutation_feature_importance(ToyModel(), bad)


def test_stability_rejects_non_finite_model_score():
    class BadModel:
        def score(self, features):
            return float("nan")

    with pytest.raises(ValueError, match="model score"):
        permutation_feature_importance(BadModel(), make_samples())
