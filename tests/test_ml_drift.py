from datetime import datetime, timezone

import pytest

from strategy.ml_drift import analyze_feature_drift
from strategy.ml_features import MLSample


def _sample(index, features):
    return MLSample(
        index=index,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        features=tuple(features),
        label=index % 2,
    )


def test_drift_is_zero_for_identical_distributions():
    train = [_sample(i, (float(i), 1.0)) for i in range(10)]
    test = [_sample(i + 10, (float(i), 1.0)) for i in range(10)]

    report = analyze_feature_drift(train, test)

    assert report.train_sample_count == 10
    assert report.test_sample_count == 10
    assert report.feature_count == 2
    assert report.features[0].psi == pytest.approx(0.0)
    assert report.features[0].mean_shift_std == pytest.approx(0.0)
    assert report.features[1].psi == pytest.approx(0.0)


def test_test_distribution_can_show_drift_without_changing_training_bins():
    train = [_sample(i, (float(i), 0.0)) for i in range(10)]
    test = [_sample(i + 10, (float(i) + 100.0, 0.0)) for i in range(10)]

    report = analyze_feature_drift(train, test, bins=5)

    assert report.features[0].psi > 0.0
    assert report.features[0].mean_shift_std > 0.0
    assert report.features[1].psi == pytest.approx(0.0)


def test_drift_rejects_feature_width_mismatch():
    train = [_sample(0, (1.0, 2.0))]
    test = [_sample(1, (1.0,))]

    with pytest.raises(ValueError, match="feature widths"):
        analyze_feature_drift(train, test)


def test_drift_rejects_invalid_configuration():
    samples = [_sample(0, (1.0,))]

    with pytest.raises(ValueError, match="bins"):
        analyze_feature_drift(samples, samples, bins=1)
    with pytest.raises(ValueError, match="epsilon"):
        analyze_feature_drift(samples, samples, epsilon=0.0)
