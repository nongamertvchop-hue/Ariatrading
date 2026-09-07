from datetime import datetime, timezone

import pytest

from live.paper_runtime import ExecutionMode, PaperAutomationRuntime, PaperRuntimeConfig, RuntimeState
from live.state_store import JsonRuntimeStateStore
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


def evaluation(minute: int, action: str = LONG, *, low: float = 100.0) -> LiveEvaluation:
    candle = Candle(101.0, 103.0, low, 102.0)
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


def test_session_does_not_reenter_on_bar_used_for_exit():
    monitor = FakeMonitor([evaluation(1), evaluation(2), evaluation(3, low=98.0)])
    runtime = PaperAutomationRuntime(monitor)

    runtime.step()
    opened = runtime.step()
    exited = runtime.step()

    assert opened is not None and opened.opened is not None
    assert exited is not None
    assert exited.closed is not None
    assert exited.opened is None
    assert runtime.snapshot().closed_trades == 1


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


def test_runtime_checkpoint_restores_pending_signal_and_opens_next_bar(tmp_path):
    store = JsonRuntimeStateStore(tmp_path / "paper-runtime.json")
    first_runtime = PaperAutomationRuntime(FakeMonitor([evaluation(1)]), state_store=store)

    first = first_runtime.step()
    assert first is not None
    assert first_runtime.snapshot().pending_signal is True
    assert store.exists()

    restarted = PaperAutomationRuntime(FakeMonitor([evaluation(2)]), state_store=store)
    restored = restarted.restore_checkpoint()
    assert restored.last_bar_time == dt(1)
    assert restored.pending_signal is True

    result = restarted.step()
    assert result is not None
    assert result.opened is not None
    assert result.opened.signal_time == dt(1)
    assert result.opened.entry_time == dt(2)


def test_runtime_checkpoint_restores_open_position_without_duplicate_trade(tmp_path):
    store = JsonRuntimeStateStore(tmp_path / "paper-runtime.json")
    first_runtime = PaperAutomationRuntime(
        FakeMonitor([evaluation(1), evaluation(2)]),
        state_store=store,
    )
    first_runtime.step()
    opened = first_runtime.step()
    assert opened is not None and opened.opened is not None
    trade_id = opened.opened.trade_id

    restarted = PaperAutomationRuntime(FakeMonitor([evaluation(3, low=98.0)]), state_store=store)
    restored = restarted.restore_checkpoint()
    assert restored.closed_trades == 0
    assert restarted.session.paper.position is not None
    assert restarted.session.paper.position.trade_id == trade_id

    result = restarted.step()
    assert result is not None
    assert result.closed is not None
    assert result.closed.trade_id == trade_id
    assert result.opened is None
    assert restarted.snapshot().closed_trades == 1


def test_corrupt_checkpoint_fails_closed(tmp_path):
    store = JsonRuntimeStateStore(tmp_path / "paper-runtime.json")
    store.save({"version": 999})
    runtime = PaperAutomationRuntime(FakeMonitor([]), state_store=store)

    with pytest.raises(ValueError, match="unsupported or invalid runtime state version"):
        runtime.restore_checkpoint()
    assert runtime.state is RuntimeState.HALTED
    assert "checkpoint restore failed" in runtime.last_error
