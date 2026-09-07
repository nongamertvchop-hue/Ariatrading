from datetime import datetime, timezone

import pytest

from live.paper_runtime import ExecutionMode, PaperAutomationRuntime, PaperRuntimeConfig, RuntimeState
from strategy.candles import Candle
from strategy.engine import EngineSignal, LONG
from strategy.journal import PaperTradeJournal
from strategy.levels_v2 import PriceZone, SUPPORT
from strategy.market_snapshot import MarketSnapshot
from strategy.realtime import LiveEvaluation
from strategy.realtime_guard import DataQuality
from strategy.realtime_supervisor import ALLOW, SupervisorDecision


def dt(minute: int) -> datetime:
    return datetime(2026, 1, 1, 0, minute, tzinfo=timezone.utc)


def evaluation(minute: int, action: str = LONG) -> LiveEvaluation:
    candle = Candle(101.0, 103.0, 100.0, 102.0)
    signal = EngineSignal(action, "confirmed", "1m", zone=PriceZone(99.0, 100.0, SUPPORT, 3))
    supervisor = SupervisorDecision(ALLOW, action == LONG, ("ok",) if action == LONG else ("blocked",))
    snapshot = MarketSnapshot(
        symbol="EURUSD",
        timeframe="1m",
        bar_time=dt(minute),
        candle=candle,
        current_close=candle.close,
        data_quality=DataQuality(True, "ok", dt(minute), 0.0),
    )
    return LiveEvaluation(
        symbol="EURUSD",
        timeframe="1m",
        evaluated_at=dt(minute),
        bar_time=dt(minute),
        signal=signal,
        support=PriceZone(99.0, 100.0, SUPPORT, 3),
        resistance=None,
        snapshot=snapshot,
        supervisor=supervisor,
    )


class FakeMonitor:
    def __init__(self, evaluations):
        self._evaluations = iter(evaluations)

    def evaluate_once(self, now=None):
        return next(self._evaluations, None)


def test_runtime_processes_automatic_paper_session():
    monitor = FakeMonitor([evaluation(1), evaluation(2)])
    runtime = PaperAutomationRuntime(monitor, config=PaperRuntimeConfig(poll_seconds=0.01))

    first = runtime.step()
    second = runtime.step()

    assert first is not None
    assert second is not None
    assert second.opened is not None
    snapshot = runtime.snapshot()
    assert snapshot.mode is ExecutionMode.PAPER
    assert snapshot.last_bar_time == dt(2)
    assert snapshot.pending_signal is False


def test_runtime_halts_on_unexpected_feed_failure():
    class BrokenMonitor:
        def evaluate_once(self, now=None):
            raise RuntimeError("feed unavailable")

    runtime = PaperAutomationRuntime(BrokenMonitor())
    with pytest.raises(RuntimeError, match="feed unavailable"):
        runtime.step()
    assert runtime.state is RuntimeState.HALTED
    assert "feed unavailable" in runtime.last_error


def test_runtime_run_can_be_bounded_without_real_sleep():
    runtime = PaperAutomationRuntime(FakeMonitor([evaluation(1)]))
    snapshot = runtime.run(max_iterations=1, sleep_fn=lambda _: None)
    assert snapshot.state is RuntimeState.STOPPED
    assert snapshot.closed_trades == 0


def test_demo_mode_is_not_accidentally_enabled():
    with pytest.raises(RuntimeError, match="no MT5 order execution adapter"):
        PaperAutomationRuntime(FakeMonitor([]), mode=ExecutionMode.DEMO)


def test_signal_identity_is_stable_and_journal_deduplicates():
    journal = PaperTradeJournal()
    signal = EngineSignal(LONG, "confirmed", "1m", zone=PriceZone(99.0, 100.0, SUPPORT, 3))
    first = journal.record_signal(
        event_time=dt(1),
        signal_time=dt(1),
        symbol="EURUSD",
        timeframe="1m",
        signal=signal,
    )
    second = journal.record_signal(
        event_time=dt(1),
        signal_time=dt(1),
        symbol="EURUSD",
        timeframe="1m",
        signal=signal,
    )
    assert first.event_id == second.event_id
    assert len(journal.events) == 1
