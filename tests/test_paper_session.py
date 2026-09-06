from datetime import datetime, timezone

from strategy.candles import Candle
from strategy.engine import EngineSignal, LONG, SHORT, WAIT
from strategy.journal import PaperTradeJournal
from strategy.levels_v2 import PriceZone, RESISTANCE, SUPPORT
from strategy.market_snapshot import MarketSnapshot
from strategy.paper import PaperTradingEngine
from strategy.paper_session import PaperSessionRunner
from strategy.realtime import LiveEvaluation
from strategy.realtime_guard import DataQuality
from strategy.realtime_supervisor import ALLOW, SupervisorDecision


def dt(minute: int) -> datetime:
    return datetime(2026, 1, 1, 0, minute, tzinfo=timezone.utc)


def zone(kind: str = SUPPORT) -> PriceZone:
    return PriceZone(low=99.0, high=100.0, kind=kind, touches=3)


def evaluation(minute: int, action: str = LONG, *, supervisor_action: str | None = None) -> LiveEvaluation:
    is_long = action == LONG
    selected_zone = zone(SUPPORT if is_long else RESISTANCE)
    candle = Candle(101.0, 103.0, 99.0, 102.0)
    signal = EngineSignal(action, "confirmed", "1m", zone=selected_zone if action in {LONG, SHORT} else None)
    if supervisor_action is None:
        supervisor_action = ALLOW if action in {LONG, SHORT} else WAIT
    supervisor = SupervisorDecision(supervisor_action, supervisor_action == ALLOW, ("ok",) if supervisor_action == ALLOW else ("blocked",))
    snapshot = MarketSnapshot(
        symbol="EURUSD",
        timeframe="1m",
        bar_time=dt(minute),
        candle=candle,
        current_close=102.0,
        data_quality=DataQuality(True, "ok", dt(minute), 0.0),
    )
    return LiveEvaluation(
        symbol="EURUSD",
        timeframe="1m",
        evaluated_at=dt(minute),
        bar_time=dt(minute),
        signal=signal,
        support=zone(SUPPORT),
        resistance=zone(RESISTANCE),
        snapshot=snapshot,
        supervisor=supervisor,
    )


class FakeMonitor:
    def __init__(self, evaluations):
        self._evaluations = iter(evaluations)

    def evaluate_once(self, now=None):
        return next(self._evaluations, None)


def test_signal_from_bar_n_opens_at_next_bar_open_only():
    first_eval = evaluation(1)
    second_eval = evaluation(2)
    runner = PaperSessionRunner(FakeMonitor([first_eval, second_eval]))

    first = runner.process_once()
    assert first is not None
    assert first.opened is None
    assert runner.paper.position is None

    second = runner.process_once()
    assert second is not None
    assert second.opened is not None
    assert second.opened.signal_time == dt(1)
    assert second.opened.entry_time == dt(2)
    assert second.opened.entry_price == second_eval.snapshot.candle.open
    assert second.opened.entry_price != second_eval.snapshot.current_close


def test_existing_position_is_managed_on_subsequent_bar():
    runner = PaperSessionRunner(
        FakeMonitor([evaluation(1), evaluation(2), evaluation(3)]),
        paper=PaperTradingEngine(reward_risk=1.0 / 6.0),
    )

    runner.process_once()
    opened_result = runner.process_once()
    assert opened_result.opened is not None

    result = runner.process_once()
    assert result is not None
    assert result.closed is not None
    assert result.closed.outcome == "WIN"
    assert runner.paper.position is None


def test_journal_contains_signal_and_open_events():
    journal = PaperTradeJournal()
    runner = PaperSessionRunner(FakeMonitor([evaluation(1), evaluation(2)]), journal=journal)
    runner.process_once()
    runner.process_once()

    event_types = [event.event_type for event in journal.events]
    assert event_types == ["SIGNAL", "SIGNAL", "OPEN"]
    assert len(journal.trade_events(1)) == 1
    assert journal.trade_events(1)[0].event_type == "OPEN"
    assert journal.trade_events(1)[0].entry_price == 101.0


def test_wait_does_not_create_pending_trade():
    runner = PaperSessionRunner(FakeMonitor([evaluation(1, WAIT)]))
    result = runner.process_once()
    assert result is not None
    assert runner.pending_signal is None
    assert runner.paper.position is None


def test_blocked_directional_signal_does_not_create_pending_trade():
    runner = PaperSessionRunner(
        FakeMonitor([evaluation(1, LONG, supervisor_action=WAIT), evaluation(2, LONG)]),
    )
    first = runner.process_once()
    assert first is not None
    assert runner.pending_signal is None

    second = runner.process_once()
    assert second is not None
    assert second.opened is None
    assert runner.paper.position is None


def test_duplicate_monitor_evaluation_does_not_replay_same_bar():
    first = evaluation(1)

    class DuplicateMonitor:
        def __init__(self):
            self.calls = 0

        def evaluate_once(self, now=None):
            self.calls += 1
            return first if self.calls <= 2 else evaluation(2)

    runner = PaperSessionRunner(DuplicateMonitor())
    first_result = runner.process_once()
    duplicate_result = runner.process_once()
    next_result = runner.process_once()

    assert first_result is not None
    assert duplicate_result is None
    assert next_result is not None
    assert len(runner.journal.events) == 2
    assert runner.paper.position is not None
    assert runner.paper.position.signal_time == dt(1)


def test_close_is_processed_before_new_pending_entry():
    # A position opened from bar 1 is hit on bar 3. The same bar's signal must
    # not open a second position immediately; any new approved signal can only
    # become pending after the existing position has been resolved.
    runner = PaperSessionRunner(
        FakeMonitor([evaluation(1), evaluation(2), evaluation(3)]),
        paper=PaperTradingEngine(reward_risk=1.0 / 6.0),
    )
    runner.process_once()
    opened = runner.process_once()
    assert opened.opened is not None

    result = runner.process_once()
    assert result.closed is not None
    assert result.opened is None
    assert runner.paper.position is None
    assert runner.pending_signal is None
