from datetime import datetime, timedelta, timezone

import pytest

from strategy.forecast import DOWN, FLAT, UP, forecast
from strategy.replay import replay_forecasts


def make_candles(n=40):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = []
    price = 100.0
    for i in range(n):
        open_price = price
        close = price + (0.35 if i % 3 else 0.20)
        high = max(open_price, close) + 0.10
        low = min(open_price, close) - 0.05
        candles.append({
            "time": start + timedelta(minutes=i),
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
        })
        price = close
    return candles


def test_forecast_uses_only_completed_history_and_probabilities_sum_to_one():
    candles = make_candles()
    result = forecast(candles)
    assert result.current_close == candles[-1]["close"]
    assert result.model == "deterministic-empirical-v1"
    for horizon in result.horizons:
        assert abs(horizon.up_probability + horizon.flat_probability + horizon.down_probability - 1.0) < 1e-9
        assert horizon.expected_close > 0
        assert horizon.direction in {UP, FLAT, DOWN}
    assert 0.0 <= result.confidence <= 1.0


def test_forecast_is_deterministic_for_same_input():
    candles = make_candles()
    assert forecast(candles) == forecast(candles)


def test_forecast_does_not_change_when_unseen_future_bar_is_appended():
    candles = make_candles()
    before = forecast(candles[:-1])
    after = forecast(candles[:-1])
    assert before == after


def test_forecast_rejects_invalid_horizons():
    with pytest.raises(ValueError):
        forecast(make_candles(), horizons=(3, 1))


def test_replay_is_chronological_and_deterministic():
    candles = make_candles(50)
    first = replay_forecasts(candles, "1m", warmup=10)
    second = replay_forecasts(candles, "1m", warmup=10)
    assert first == second
    assert first.count > 0
    assert all(point.index < len(candles) for point in first.points)
