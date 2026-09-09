from datetime import datetime, timedelta, timezone

import pytest

from strategy.realtime import LiveBar, RealtimeMonitor


class FakeFeed:
    def __init__(self, bars):
        self.bars = bars

    def closed_bars(self, symbol, timeframe, count):
        return self.bars[-count:]


def make_bars(count=20):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = []
    for i in range(count):
        base = 1.10 + (i % 5) * 0.0001
        bars.append(
            LiveBar(
                start + timedelta(minutes=i),
                base,
                base + 0.0004,
                base - 0.0002,
                base + 0.0001,
            )
        )
    return bars


def test_live_monitor_uses_closed_bars_only_and_returns_evaluation():
    bars = make_bars()
    now = bars[-1].time + timedelta(seconds=30)

    result = RealtimeMonitor(FakeFeed(bars), "EURUSD", "1m", lookback=20).evaluate_once(now=now)

    assert result is not None
    assert result.symbol == "EURUSD"
    assert result.timeframe == "1m"
    assert result.bar_time == bars[-1].time
    assert result.signal.action in {"LONG", "SHORT", "WAIT"}
    assert result.signal.state in {"APPROACH", "TEST", "RECLAIM", "REJECT", "CONFIRM", "BROKEN"}
    assert result.event_id.startswith("sig_")
    assert len(result.event_id) == 36
    assert result.snapshot is not None
    assert result.snapshot.symbol == "EURUSD"
    assert result.snapshot.bar_time == bars[-1].time
    assert result.snapshot.current_close == bars[-1].close
    assert result.snapshot.data_quality is not None
    assert result.snapshot.data_quality.ok is True
    assert result.snapshot.data_quality.latest_time == bars[-1].time
    assert result.snapshot.ready is True
    assert result.supervisor is not None


def test_live_monitor_event_identity_is_stable_for_same_decision():
    bars = make_bars()
    first_monitor = RealtimeMonitor(FakeFeed(bars), "EURUSD", "1m", lookback=20)
    second_monitor = RealtimeMonitor(FakeFeed(bars), "EURUSD", "1m", lookback=20)
    now = bars[-1].time + timedelta(seconds=30)

    first = first_monitor.evaluate_once(now=now)
    second = second_monitor.evaluate_once(now=now)

    assert first is not None
    assert second is not None
    assert first.event_id == second.event_id


def test_live_monitor_does_not_evaluate_same_closed_bar_twice():
    bars = make_bars()
    feed = FakeFeed(bars)
    monitor = RealtimeMonitor(feed, "EURUSD", "1m", lookback=20)
    now = bars[-1].time + timedelta(seconds=30)

    first = monitor.evaluate_once(now=now)
    second = monitor.evaluate_once(now=now)

    assert first is not None
    assert second is None
    assert monitor.last_bar_time == bars[-1].time


def test_live_monitor_evaluates_after_a_new_closed_bar_arrives():
    bars = make_bars()
    feed = FakeFeed(bars)
    monitor = RealtimeMonitor(feed, "EURUSD", "1m", lookback=20)
    first_now = bars[-1].time + timedelta(seconds=30)
    first = monitor.evaluate_once(now=first_now)

    feed.bars.append(
        LiveBar(
            bars[-1].time + timedelta(minutes=1),
            1.1010,
            1.1014,
            1.1008,
            1.1012,
        )
    )
    second_now = feed.bars[-1].time + timedelta(seconds=30)
    second = monitor.evaluate_once(now=second_now)

    assert first is not None
    assert second is not None
    assert second.bar_time == feed.bars[-1].time
    assert second.bar_time > first.bar_time
    assert second.event_id != first.event_id


def test_live_monitor_does_not_advance_cursor_when_guard_rejects_stale_data():
    bars = make_bars()
    feed = FakeFeed(bars)
    monitor = RealtimeMonitor(feed, "EURUSD", "1m", lookback=20)
    first_now = bars[-1].time + timedelta(seconds=30)
    first = monitor.evaluate_once(now=first_now)
    assert first is not None

    feed.bars = feed.bars[:-1]
    with pytest.raises(RuntimeError, match="realtime data rejected"):
        monitor.evaluate_once(now=bars[-1].time + timedelta(minutes=1, seconds=30))

    assert monitor.last_bar_time == bars[-1].time


def test_nearest_zone_helpers_prefer_closest_zone_then_touches():
    from strategy.levels_v2 import PriceZone, RESISTANCE, SUPPORT

    supports = [
        PriceZone(1.0900, 1.0910, SUPPORT, 2),
        PriceZone(1.0950, 1.0960, SUPPORT, 4),
        PriceZone(1.0980, 1.0990, SUPPORT, 3),
    ]
    resistances = [
        PriceZone(1.1010, 1.1020, RESISTANCE, 2),
        PriceZone(1.1040, 1.1050, RESISTANCE, 4),
        PriceZone(1.1080, 1.1090, RESISTANCE, 3),
    ]

    assert RealtimeMonitor._nearest_support(1.1030, supports) == supports[2]
    assert RealtimeMonitor._nearest_resistance(1.1030, resistances) == resistances[1]


def test_live_monitor_rejects_invalid_timeframe_early():
    bars = make_bars()
    try:
        RealtimeMonitor(FakeFeed(bars), "EURUSD", "2m", lookback=20)
    except ValueError as exc:
        assert "unsupported timeframe" in str(exc)
    else:
        raise AssertionError("expected unsupported timeframe error")


def test_live_monitor_rejects_feed_timestamp_misalignment():
    bars = make_bars()
    bars[-1] = LiveBar(
        bars[-1].time + timedelta(seconds=30),
        bars[-1].open,
        bars[-1].high,
        bars[-1].low,
        bars[-1].close,
    )
    monitor = RealtimeMonitor(FakeFeed(bars), "EURUSD", "1m", lookback=20)
    now = bars[-1].time + timedelta(seconds=30)

    with pytest.raises(RuntimeError, match="feed integrity rejected"):
        monitor.evaluate_once(now=now)


def test_live_monitor_rejects_non_finite_feed_value():
    bars = make_bars()
    bars[-1] = LiveBar(
        bars[-1].time,
        float("nan"),
        bars[-1].high,
        bars[-1].low,
        bars[-1].close,
    )
    monitor = RealtimeMonitor(FakeFeed(bars), "EURUSD", "1m", lookback=20)
    now = bars[-1].time + timedelta(seconds=30)

    with pytest.raises(RuntimeError, match="feed integrity rejected"):
        monitor.evaluate_once(now=now)
