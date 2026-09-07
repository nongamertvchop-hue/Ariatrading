from datetime import datetime, timedelta, timezone

import pytest

from strategy.engine import EngineSignal, LONG, SHORT
from strategy.levels_v2 import PriceZone, SUPPORT, RESISTANCE
from strategy.ml_features import build_signal_sample, extract_signal_features


def make_candles(n=12):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = []
    for i in range(n):
        close = 1.1000 + i * 0.0010
        candles.append(
            {
                "time": start + timedelta(minutes=i),
                "open": close - 0.0003,
                "high": close + 0.0007,
                "low": close - 0.0008,
                "close": close,
            }
        )
    return candles


def make_signal(action=LONG):
    zone = PriceZone(
        low=1.1030,
        high=1.1050,
        kind=SUPPORT if action == LONG else RESISTANCE,
        touches=3,
    )
    return EngineSignal(
        action=action,
        reason="test signal",
        timeframe="15m",
        zone=zone,
        score=None,
    )


@pytest.mark.parametrize("index", [5, 8])
@pytest.mark.parametrize("action", [LONG, SHORT])
def test_signal_features_are_prefix_invariant(index, action):
    candles = make_candles()
    signal = make_signal(action)

    baseline = extract_signal_features(candles, index, signal)

    mutated = [dict(candle) for candle in candles]
    for future_index in range(index + 1, len(mutated)):
        mutated[future_index]["open"] += 0.2500
        mutated[future_index]["high"] += 0.5000
        mutated[future_index]["low"] -= 0.4000
        mutated[future_index]["close"] -= 0.3000

    after_future_mutation = extract_signal_features(mutated, index, signal)

    assert after_future_mutation == baseline


def test_future_mutation_can_change_label_without_changing_features():
    candles = make_candles()
    index = 8
    signal = make_signal(LONG)

    original_features = extract_signal_features(candles, index, signal)
    original_sample = build_signal_sample(candles, index, signal, horizon_bars=3)

    mutated = [dict(candle) for candle in candles]
    mutated[index + 3]["close"] = mutated[index]["close"] - 0.0100
    mutated[index + 3]["open"] = mutated[index + 3]["close"] + 0.0003
    mutated[index + 3]["high"] = mutated[index + 3]["close"] + 0.0007
    mutated[index + 3]["low"] = mutated[index + 3]["close"] - 0.0008

    mutated_features = extract_signal_features(mutated, index, signal)
    mutated_sample = build_signal_sample(mutated, index, signal, horizon_bars=3)

    assert mutated_features == original_features
    assert mutated_sample.label != original_sample.label
