from datetime import datetime, timedelta, timezone

import pytest

from strategy.paper_replay import replay_paper_session


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


def test_paper_replay_is_deterministic():
    candles = make_candles()
    first = replay_paper_session(candles, "TEST", "1m", lookback=20)
    second = replay_paper_session(candles, "TEST", "1m", lookback=20)

    assert first == second
    assert first.count == len(candles) - 4
    assert first.realized_r == first.final_state["paper"]["account"]["realized_r"]


def test_paper_replay_preserves_next_bar_entry_boundary():
    candles = make_candles()
    result = replay_paper_session(candles, "TEST", "1m", lookback=20)

    for item in result.results:
        if item.opened is not None:
            assert item.opened.entry_time > item.opened.signal_time
            assert item.opened.entry_price == item.evaluation.snapshot.candle.open


def test_paper_replay_uses_only_historical_prefix():
    candles = make_candles(30)
    prefix = candles[:20]
    mutated = [dict(candle) for candle in candles]
    for candle in mutated[20:]:
        candle["open"] += 1000.0
        candle["high"] += 1000.0
        candle["low"] += 1000.0
        candle["close"] += 1000.0

    prefix_result = replay_paper_session(prefix, "TEST", "1m", lookback=20)
    full_result = replay_paper_session(mutated, "TEST", "1m", lookback=20)

    assert prefix_result.results == full_result.results[:prefix_result.count]


def test_paper_replay_rejects_invalid_start_index():
    with pytest.raises(ValueError, match="start_index"):
        replay_paper_session(make_candles(10), "TEST", "1m", start_index=10)


def test_paper_replay_rejects_lookback_below_realtime_monitor_contract():
    with pytest.raises(ValueError, match="lookback"):
        replay_paper_session(make_candles(), "TEST", "1m", lookback=9)
