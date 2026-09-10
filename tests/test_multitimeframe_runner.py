from datetime import datetime, timedelta, timezone

import pytest

from strategy.multitimeframe_runner import run_multitimeframe_research
from strategy.timeframe import SUPPORTED_TIMEFRAMES


def make_candles(timeframe_minutes: int = 15, n: int = 80):
    start = datetime(2026, 1, 5, tzinfo=timezone.utc)
    price = 1.1000
    rows = []
    for i in range(n):
        move = 0.0002 if i % 2 == 0 else -0.0001
        rows.append(
            {
                "time": start + timedelta(minutes=timeframe_minutes * i),
                "open": price,
                "high": price + 0.0010,
                "low": price - 0.0010,
                "close": price + move,
            }
        )
        price += move
    return rows


def make_dataset():
    durations = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1D": 1440}
    return {timeframe: make_candles(minutes) for timeframe, minutes in durations.items()}


def add_gap(candles, start_index: int, gap: timedelta):
    for index in range(start_index, len(candles)):
        candles[index]["time"] += gap


def test_runner_validates_all_supported_timeframes():
    result = run_multitimeframe_research(
        make_dataset(),
        history_bars=40,
        test_bars=10,
    )

    assert set(result.results) == set(SUPPORTED_TIMEFRAMES)
    assert result.report.timeframe_count == len(SUPPORTED_TIMEFRAMES)
    assert len(result.inputs) == len(SUPPORTED_TIMEFRAMES)
    assert all(item.integrity.ok for item in result.inputs)


def test_runner_rejects_missing_timeframe():
    dataset = make_dataset()
    dataset.pop("1D")

    with pytest.raises(ValueError, match="timeframe set mismatch"):
        run_multitimeframe_research(
            dataset,
            history_bars=40,
            test_bars=10,
        )


def test_runner_rejects_out_of_order_bars():
    dataset = make_dataset()
    dataset["15m"][10], dataset["15m"][11] = dataset["15m"][11], dataset["15m"][10]

    with pytest.raises(ValueError, match="feed integrity failed for 15m"):
        run_multitimeframe_research(
            dataset,
            history_bars=40,
            test_bars=10,
        )


def test_runner_allows_weekend_like_gaps_by_default():
    dataset = make_dataset()
    add_gap(dataset["15m"], 20, timedelta(hours=1))

    # The structural feed is still chronological; default research mode does not
    # require every interval because FX feeds can contain legitimate session gaps.
    result = run_multitimeframe_research(
        dataset,
        history_bars=40,
        test_bars=10,
    )
    assert result.inputs[2].integrity.ok


def test_runner_can_require_contiguous_feed():
    dataset = make_dataset()
    add_gap(dataset["15m"], 20, timedelta(hours=1))

    with pytest.raises(ValueError, match="feed integrity failed for 15m"):
        run_multitimeframe_research(
            dataset,
            history_bars=40,
            test_bars=10,
            require_contiguous=True,
        )


def test_runner_rejects_non_datetime_candle_time():
    dataset = make_dataset()
    dataset["1m"][0]["time"] = "2026-01-05T00:00:00Z"

    with pytest.raises(ValueError, match="require timezone-aware datetime"):
        run_multitimeframe_research(
            dataset,
            history_bars=40,
            test_bars=10,
        )
