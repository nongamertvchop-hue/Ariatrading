from datetime import datetime, timedelta, timezone

import pytest

from strategy.candles import Candle
from strategy.feed_integrity import validate_feed_batch


class Bar(Candle):
    """Candle subclass used only to provide the expected feed shape."""

    pass


def _bars(count: int = 3):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        Bar(
            1.0 + i * 0.0001,
            1.1 + i * 0.0001,
            0.9 + i * 0.0001,
            1.05 + i * 0.0001,
            # This constructor shape is intentionally invalid if Candle has no time.
        )
        for i in range(count)
    ]


class TimedBar:
    def __init__(self, time, open_, high, low, close):
        self.time = time
        self.open = open_
        self.high = high
        self.low = low
        self.close = close


def _timed_bars(times):
    return [TimedBar(t, 1.0, 1.1, 0.9, 1.05) for t in times]


def test_valid_hourly_batch_passes():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    report = validate_feed_batch(
        _timed_bars([start, start + timedelta(hours=1), start + timedelta(hours=2)]),
        "1h",
    )
    assert report.ok
    assert report.checked_bars == 3


def test_duplicate_timestamp_is_rejected():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    report = validate_feed_batch(_timed_bars([start, start, start + timedelta(hours=1)]), "1h")
    assert not report.ok
    assert report.duplicate_count == 1


def test_out_of_order_timestamp_is_rejected():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    report = validate_feed_batch(_timed_bars([start, start + timedelta(hours=2), start + timedelta(hours=1)]), "1h")
    assert not report.ok
    assert report.out_of_order_count == 1


def test_misaligned_timestamp_is_rejected():
    start = datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc)
    report = validate_feed_batch(_timed_bars([start]), "1h")
    assert not report.ok
    assert report.misaligned_count == 1


def test_non_utc_timestamp_is_rejected_by_default():
    start = datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=7)))
    report = validate_feed_batch(_timed_bars([start]), "1h")
    assert not report.ok
    assert "UTC" in report.reason


def test_empty_feed_is_rejected():
    report = validate_feed_batch([], "1h")
    assert not report.ok


def test_bad_ohlc_is_rejected():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    report = validate_feed_batch([TimedBar(start, 1.0, 0.9, 1.0, 1.0)], "1h")
    assert not report.ok
    assert "OHLC" in report.reason
