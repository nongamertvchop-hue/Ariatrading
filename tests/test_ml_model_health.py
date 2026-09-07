from datetime import datetime, timezone

import pytest

from strategy.ml_features import MLSample
from strategy.ml_model_health import analyze_model_health


class FakeModel:
    def score(self, features):
        return float(features[0])


def _sample(index, score, label):
    return MLSample(
        index=index,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        features=(float(score), 0.0),
        label=label,
    )


def test_health_reports_performance_and_calibration():
    train = [_sample(0, 0.1, 0), _sample(1, 0.9, 1), _sample(2, 0.2, 0), _sample(3, 0.8, 1)]
    test = [_sample(4, 0.2, 0), _sample(5, 0.8, 1), _sample(6, 0.3, 0), _sample(7, 0.7, 1)]

    report = analyze_model_health(FakeModel(), train, test, bins=5)

    assert report.train.samples == 4
    assert report.test.samples == 4
    assert report.train.accuracy == pytest.approx(1.0)
    assert report.test.accuracy == pytest.approx(1.0)
    assert report.train.brier_score == pytest.approx((0.1**2 + 0.1**2 + 0.2**2 + 0.2**2) / 4)
    assert report.accuracy_delta == pytest.approx(0.0)
    assert report.test.calibration_error > 0.0
    assert len(report.test.calibration_bins) == 4


def test_health_detects_oos_performance_degradation():
    train = [_sample(0, 0.1, 0), _sample(1, 0.9, 1), _sample(2, 0.2, 0), _sample(3, 0.8, 1)]
    test = [_sample(4, 0.9, 0), _sample(5, 0.8, 0), _sample(6, 0.1, 1), _sample(7, 0.2, 1)]

    report = analyze_model_health(FakeModel(), train, test)

    assert report.accuracy_delta < 0.0
    assert report.positive_precision_delta < 0.0
    assert report.positive_recall_delta < 0.0


def test_health_rejects_invalid_scores_and_feature_width():
    class BadModel:
        def score(self, features):
            return 1.5

    samples = [_sample(0, 0.1, 0), _sample(1, 0.9, 1)]
    with pytest.raises(ValueError, match="between 0 and 1"):
        analyze_model_health(BadModel(), samples, samples)

    with pytest.raises(ValueError, match="feature widths"):
        analyze_model_health(FakeModel(), samples, [MLSsample for MLSsample in ()])


def test_health_rejects_invalid_bin_count():
    samples = [_sample(0, 0.1, 0), _sample(1, 0.9, 1)]
    with pytest.raises(ValueError, match="bins"):
        analyze_model_health(FakeModel(), samples, samples, bins=1)
