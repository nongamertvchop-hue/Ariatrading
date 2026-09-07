from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from strategy.engine import EngineSignal, LONG, WAIT
from strategy.mtf import MultiTimeframeContext
from strategy.mtf_paper_comparison import _MtfFilterMonitor, _metrics
from strategy.paper_session import PaperSessionResult
from strategy.journal import JournalEvent


@dataclass
class FakeMonitor:
    evaluation: object

    def evaluate_once(self, now=None):
        return self.evaluation


def _evaluation(action=LONG):
    from types import SimpleNamespace

    return SimpleNamespace(
        symbol="TEST",
        timeframe="15m",
        evaluated_at=datetime(2026, 1, 1, 0, 15, tzinfo=timezone.utc),
        bar_time=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        signal=EngineSignal(action, "setup", "15m"),
        support=None,
        resistance=None,
        forecast=None,
        data_quality="ok",
        supervisor=None,
        snapshot=object(),
    )


def test_mtf_filter_blocks_conflicting_direction(monkeypatch):
    context = MultiTimeframeContext("15m", "BEARISH", "BEARISH", "BULLISH", "BEARISH")
    captured = {}

    def fake_context(candles, timeframe, timestamp):
        captured["timestamp"] = timestamp
        return context

    monkeypatch.setattr(
        "strategy.mtf_paper_comparison.build_timestamp_aligned_mtf_context",
        fake_context,
    )
    monitor = _MtfFilterMonitor(FakeMonitor(_evaluation(LONG)), {"15m": []})
    result = monitor.evaluate_once()

    assert result.signal.action == WAIT
    assert result.signal.protection == "BLOCKED"
    assert "alignment=BEARISH" in result.signal.reason
    assert captured["timestamp"] == datetime(2026, 1, 1, 0, 15, tzinfo=timezone.utc)


def test_mtf_filter_preserves_supported_direction(monkeypatch):
    context = MultiTimeframeContext("15m", "BULLISH", "BULLISH", "BULLISH", "BULLISH")
    monkeypatch.setattr(
        "strategy.mtf_paper_comparison.build_timestamp_aligned_mtf_context",
        lambda candles, timeframe, timestamp: context,
    )
    evaluation = _evaluation(LONG)
    result = _MtfFilterMonitor(FakeMonitor(evaluation), {"15m": []}).evaluate_once()

    assert result == evaluation


def test_non_directional_signal_is_never_created_by_mtf_filter(monkeypatch):
    called = False

    def fail_if_called(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("MTF context must not be evaluated for WAIT")

    monkeypatch.setattr(
        "strategy.mtf_paper_comparison.build_timestamp_aligned_mtf_context",
        fail_if_called,
    )
    result = _MtfFilterMonitor(FakeMonitor(_evaluation(WAIT)), {"15m": []}).evaluate_once()

    assert result.signal.action == WAIT
    assert called is False


def test_metrics_use_closed_trade_r_values():
    from strategy.paper import PaperPosition
    from types import SimpleNamespace

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    signal = JournalEvent(
        event_time=now,
        event_type="SIGNAL",
        symbol="TEST",
        timeframe="15m",
        action=LONG,
        reason="setup",
        event_id="signal-1",
        signal_time=now,
    )
    position = PaperPosition(
        trade_id=1, direction=LONG, signal_time=now,
        entry_time=now + timedelta(minutes=15), entry_price=100.0,
        stop=99.0, target=102.0, risk_distance=1.0,
        status="CLOSED", exit_time=now + timedelta(minutes=30),
        exit_price=102.0, outcome="WIN", r_multiple=2.0,
        bars_held=1,
    )
    result = PaperSessionResult(
        evaluation=SimpleNamespace(symbol="TEST", timeframe="15m", bar_time=now),
        opened=position, closed=position, signal_event=signal,
        open_event=None, close_event=None,
    )
    metrics = _metrics((result,))

    assert metrics.signal_count == 1
    assert metrics.opened_count == 1
    assert metrics.closed_count == 1
    assert metrics.wins == 1
    assert metrics.losses == 0
    assert metrics.realized_r == 2.0
    assert metrics.win_rate == 1.0
    assert metrics.mean_r == 2.0
