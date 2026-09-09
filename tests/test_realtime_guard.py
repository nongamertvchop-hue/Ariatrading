from datetime import datetime, timedelta, timezone

import pytest

from strategy.realtime import LiveBar, RealtimeMonitor
from strategy.realtime_guard import RealtimeGuard


class Feed:
    def __init__(self, bars):
        self.bars = bars

    def closed_bars(self, symbol, timeframe, count):
        return self.bars[-count:]


def bars(n=20):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        LiveBar(start + timedelta(minutes=i), 100 + i, 100.2 + i, 99.8 + i, 100.1 + i)
        for i in range(n)
    ]


def test_guard_accepts_fresh_chronological_bars():
    data = bars()
    guard = RealtimeGuard("1m")
    quality = guard.validate(data, now=data[-1].time + timedelta(seconds=30))
    assert quality.ok
    assert quality.reason == "ok"


def test_guard_rejects_duplicate_after_accept():
    data = bars()
    guard = RealtimeGuard("1m")
    now = data[-1].time + timedelta(seconds=30)
    guard.accept(data, now=now)
    quality = guard.validate(data, now=now)
    assert not quality.ok
    assert quality.reason == "duplicate or old closed bar"


def test_guard_rejects_stale_feed():
    data = bars()
    guard = RealtimeGuard("1m", max_staleness_bars=2)
    quality = guard.validate(data, now=data[-1].time + timedelta(minutes=3))
    assert not quality.ok
    assert quality.reason == "feed is stale"


def test_guard_rejects_future_timestamp():
    data = bars()
    guard = RealtimeGuard("1m")
    quality = guard.validate(data, now=data[-1].time - timedelta(seconds=1))
    assert not quality.ok
    assert quality.reason == "latest bar timestamp is in the future"


def test_guard_rejects_naive_bar_timestamp_without_type_error():
    data = bars()
    bad = list(data)
    bad[-1] = LiveBar.__new__(LiveBar)
    object.__setattr__(bad[-1], "time", data[-1].time.replace(tzinfo=None))
    object.__setattr__(bad[-1], "open", data[-1].open)
    object.__setattr__(bad[-1], "high", data[-1].high)
    object.__setattr__(bad[-1], "low", data[-1].low)
    object.__setattr__(bad[-1], "close", data[-1].close)
    quality = RealtimeGuard("1m").validate(bad, now=data[-1].time + timedelta(seconds=30))
    assert not quality.ok
    assert quality.reason == "bar timestamp must be timezone-aware"


def test_guard_rejects_naive_now_explicitly():
    data = bars()
    with pytest.raises(ValueError, match="now must be timezone-aware"):
        RealtimeGuard("1m").validate(data, now=data[-1].time.replace(tzinfo=None))


def test_guard_rejects_bad_ohlc_geometry():
    data = bars()
    bad = list(data)
    bad[-1] = LiveBar.__new__(LiveBar)
    object.__setattr__(bad[-1], "time", data[-1].time)
    object.__setattr__(bad[-1], "open", 100.0)
    object.__setattr__(bad[-1], "high", 99.0)
    object.__setattr__(bad[-1], "low", 98.0)
    object.__setattr__(bad[-1], "close", 100.0)
    quality = RealtimeGuard("1m").validate(bad, now=data[-1].time + timedelta(seconds=30))
    assert not quality.ok
    assert quality.reason == "invalid OHLC geometry"


def test_monitor_exposes_forecast_and_rejects_stale_data():
    data = bars(40)
    monitor = RealtimeMonitor(Feed(data), "TEST", "1m", lookback=30)
    result = monitor.evaluate_once(now=data[-1].time + timedelta(seconds=30))
    assert result is not None
    assert result.forecast is not None
    assert result.data_quality == "ok"
    assert monitor.evaluate_once(now=data[-1].time + timedelta(seconds=30)) is None
    with pytest.raises(RuntimeError, match="feed is stale"):
        monitor = RealtimeMonitor(Feed(data), "TEST", "1m", lookback=30)
        monitor.evaluate_once(now=data[-1].time + timedelta(minutes=3))
