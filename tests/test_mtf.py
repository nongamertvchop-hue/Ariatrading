from datetime import datetime, timedelta, timezone

from strategy.market_structure import BULLISH, BEARISH, MarketStructure
from strategy.mtf import (
    build_mtf_context,
    build_timestamp_aligned_mtf_context,
    closed_candles_at,
    mtf_direction_score,
)


def structure(bias):
    return MarketStructure(bias, (), (), ())


def test_bullish_mtf_alignment():
    context = build_mtf_context(
        {"15m": structure(BULLISH), "1h": structure(BULLISH), "4h": structure(BULLISH)},
        "15m",
    )
    assert context.alignment == BULLISH
    assert mtf_direction_score("LONG", context) == 10


def test_mixed_mtf_is_not_bullish():
    context = build_mtf_context(
        {"15m": structure(BULLISH), "1h": structure(BEARISH), "4h": structure(BULLISH)},
        "15m",
    )
    assert context.alignment != BULLISH
    assert mtf_direction_score("LONG", context) == 0


def bullish_hourly_bars():
    values = [
        (10, 8),
        (12, 9),
        (11, 7),
        (13, 10),
        (12, 8),
        (14, 11),
        (13, 9),
        (15, 12),
        (14, 10),
    ]
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        {
            "time": start + timedelta(hours=i),
            "open": low + 0.2,
            "high": high,
            "low": low,
            "close": low + 0.4,
        }
        for i, (high, low) in enumerate(values)
    ]


def test_closed_candles_at_excludes_forming_higher_timeframe_bar():
    bars = bullish_hourly_bars()
    entry_time = bars[7]["time"] + timedelta(minutes=30)

    closed = closed_candles_at(bars, "1h", entry_time)

    assert len(closed) == 7
    assert closed[-1]["time"] == bars[6]["time"]


def test_timestamp_aligned_mtf_does_not_use_future_higher_timeframe_data():
    higher = bullish_hourly_bars()
    entry_time = higher[7]["time"] + timedelta(minutes=30)
    entry_bars = [
        {
            "time": datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=15 * i),
            "open": 1.0,
            "high": 1.1,
            "low": 0.9,
            "close": 1.05,
        }
        for i in range(40)
    ]

    context = build_timestamp_aligned_mtf_context(
        {"15m": entry_bars, "1h": higher},
        "15m",
        entry_time,
        strength=1,
    )

    assert context.middle_bias == BULLISH
    assert context.higher_bias == BULLISH
    assert context.alignment == BULLISH
