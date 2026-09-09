from datetime import datetime, timedelta, timezone

import pytest

from strategy.engine import EngineSignal, LONG, WAIT
from strategy.realtime import LiveEvaluation
from strategy.realtime_replay import (
    RealtimeReplayResult,
    label_replay_outcomes,
    replay_realtime_monitor,
)


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


def test_replay_outcomes_match_by_event_bar_and_ignore_future_beyond_resolution():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    signal_time = start + timedelta(minutes=1)
    evaluation = LiveEvaluation(
        "TEST",
        "1m",
        signal_time + timedelta(seconds=1),
        signal_time,
        EngineSignal(LONG, "test", "1m", entry_reference=100.0, stop_reference=99.0),
        None,
        None,
    )
    replay = RealtimeReplayResult("TEST", "1m", (evaluation,))
    candles = [
        {"time": start, "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.2},
        {"time": signal_time, "open": 100.2, "high": 100.4, "low": 99.9, "close": 100.1},
        {"time": start + timedelta(minutes=2), "open": 100.1, "high": 102.0, "low": 100.0, "close": 101.5},
        {"time": start + timedelta(minutes=3), "open": 101.5, "high": 150.0, "low": 101.0, "close": 149.0},
    ]

    outcomes = label_replay_outcomes(candles, replay, target_r_multiple=2.0, max_bars=20)

    assert len(outcomes) == 1
    assert outcomes[0].event_id == evaluation.event_id
    assert outcomes[0].outcome == "WIN"
    assert outcomes[0].bars_to_resolution == 1


def test_wait_replay_outcome_is_invalid_and_preserves_event_identity():
    signal_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    evaluation = LiveEvaluation(
        "TEST",
        "1m",
        signal_time + timedelta(seconds=1),
        signal_time,
        EngineSignal(WAIT, "test", "1m"),
        None,
        None,
    )
    replay = RealtimeReplayResult("TEST", "1m", (evaluation,))

    outcomes = label_replay_outcomes(
        [
            {"time": signal_time, "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.2},
        ],
        replay,
    )

    assert outcomes[0].event_id == evaluation.event_id
    assert outcomes[0].outcome == "INVALID"


def test_realtime_replay_rejects_incompatible_lookback():
    with pytest.raises(ValueError, match="lookback"):
        replay_realtime_monitor(make_candles(12), "TEST", "1m", lookback=5)


def test_realtime_replay_rejects_invalid_start_index():
    with pytest.raises(ValueError, match="start_index"):
        replay_realtime_monitor(make_candles(10), "TEST", "1m", start_index=10)
