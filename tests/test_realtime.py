from datetime import datetime, timedelta, timezone

from strategy.realtime import LiveBar, RealtimeMonitor


class FakeFeed:
    def __init__(self, bars):
        self.bars = bars

    def closed_bars(self, symbol, timeframe, count):
        return self.bars[-count:]


def test_live_monitor_uses_closed_bars_only_and_returns_evaluation():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = []
    for i in range(20):
        base = 1.10 + (i % 5) * 0.0001
        bars.append(LiveBar(start + timedelta(minutes=i), base, base + 0.0004, base - 0.0002, base + 0.0001))

    result = RealtimeMonitor(FakeFeed(bars), "EURUSD", "1m", lookback=20).evaluate_once()

    assert result.symbol == "EURUSD"
    assert result.timeframe == "1m"
    assert result.bar_time == bars[-1].time
    assert result.signal.action in {"LONG", "SHORT", "WAIT"}
