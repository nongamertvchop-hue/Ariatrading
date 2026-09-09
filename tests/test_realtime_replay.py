from datetime import datetime, timedelta, timezone

import pytest

from strategy.realtime_replay import replay_realtime_monitor


def make_candles(n=40):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    data = []
    price = 100.0
    for i in range(n):
        move = 0.2 if i % 2 == 0 else -0.1
        data.append(
            {
                "time": start + timedelta(minutes=i),
                "open": price,
                "high": price + 0.5,
                "low": price - 0.5,
                "close": price + move,
            }
        )
        price += move
    return data


def test_realtime_replay_is_deterministic():
    candles = make_candles()
    first = replay_realtime_monitor(candles, "TEST", "1m", lookback=20)
    second = replay_realtime_monitor(candles, "TEST", "1m", lookback=20)

    assert first == second
    assert first.count == len(candles) - 4
    assert len(first.event_ids) == first.count
    assert all(event_id.startswith("sig_") for event_id in first.event_ids)
    assert len(set(first.event_ids)) == first.count


def test_realtime_replay_uses_only_historical_prefix():
    candles = make_candles(30)
    prefix = candles[:20]
    mutated = [dict(candle) for candle in candles]
    for candle in mutated[20:]:
        candle["open"] += 1000.0
        candle["high"] += 1000.0
        candle["low"] += 1000.0
        candle["close"] += 1000.0

    prefix_result = replay_realtime_monitor(prefix, "TEST", "1m", lookback=20)
    full_result = replay_realtime_monitor(mutated, "TEST", "1m", lookback=20)

    assert prefix_result.evaluations == full_result.evaluations[:prefix_result.count]
    assert prefix_result.event_ids == full_result.event_ids[:prefix_result.count]


def test_realtime_replay_event_identity_changes_with_closed_bar():
    candles = make_candles(12)
    baseline = replay_realtime_monitor(candles, "TEST", "1m", lookback=10)
    mutated = [dict(candle) for candle in candles]
    mutated[-1]["close"] += 1.0
    mutated[-1]["high"] = max(mutated[-1]["high"], mutated[-1]["close"])
    changed = replay_realtime_monitor(mutated, "TEST", "1m", lookback=10)

    assert baseline.event_ids[-1] != changed.event_ids[-1]


def test_realtime_replay_rejects_invalid_start_index():
    with pytest.raises(ValueError, match="start_index"):
        replay_realtime_monitor(make_candles(10), "TEST", "1m", start_index=10)
