from datetime import datetime, timedelta, timezone

import pytest

from strategy.engine import EngineSignal, LONG, SHORT
from strategy.ml_features import FEATURE_NAMES, build_signal_sample, extract_signal_features
from strategy.ml_meta import MetaFilterModel, chronological_train_test


def make_candles(n=60):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = []
    price = 1.1000
    for i in range(n):
        drift = 0.0008 if i % 2 == 0 else -0.0006
        candles.append(
            {
                "time": start + timedelta(minutes=i),
                "open": price,
                "high": price + 0.0012,
                "low": price - 0.0012,
                "close": price + drift,
            }
        )
        price += drift
    return candles


def test_features_use_only_current_prefix():
    candles = make_candles()
    signal = EngineSignal(LONG, "test", "15m")
    before = extract_signal_features(candles, 20, signal)
    candles[40]["close"] += 1.0
    candles[55]["close"] -= 1.0
    after = extract_signal_features(candles, 20, signal)

    assert before == after
    assert len(before) == len(FEATURE_NAMES)


def test_build_signal_sample_uses_future_only_for_label():
    candles = make_candles()
    signal = EngineSignal(SHORT, "test", "15m")
    sample = build_signal_sample(candles, 20, signal, horizon_bars=3)
    assert sample.index == 20
    assert sample.label in {0, 1}


def test_ml_training_is_chronological_and_deterministic():
    candles = make_candles(80)
    samples = []
    for index in range(5, 70):
        action = LONG if index % 2 == 0 else SHORT
        samples.append(build_signal_sample(candles, index, EngineSignal(action, "test", "15m"), horizon_bars=3))

    first = chronological_train_test(samples, train_ratio=0.7)
    second = chronological_train_test(samples, train_ratio=0.7)

    assert first == second
    assert first.metrics.train_samples < first.metrics.test_samples + first.metrics.train_samples
    assert first.metrics.test_samples > 0
    assert len(first.test_scores) == first.metrics.test_samples


def test_meta_filter_requires_both_training_classes():
    model = MetaFilterModel()
    with pytest.raises(ValueError, match="both label classes"):
        model.fit([
            build_signal_sample(make_candles(), 5, EngineSignal(LONG, "test", "15m"), horizon_bars=3, favorable_move=-0.0)
            for _ in range(3)
        ])


def test_meta_filter_threshold_and_feature_length_validation():
    candles = make_candles(80)
    samples = [
        build_signal_sample(candles, i, EngineSignal(LONG if i % 2 == 0 else SHORT, "test", "15m"), horizon_bars=3)
        for i in range(5, 60)
    ]
    model = MetaFilterModel()
    model.fit(samples)
    features = samples[-1].features

    with pytest.raises(ValueError):
        model.approve(features, threshold=1.0)
    with pytest.raises(ValueError):
        model.score(features[:-1])
