from datetime import datetime, timezone

from strategy.candles import Candle
from strategy.engine import EngineSignal, LONG, WAIT
from strategy.journal import PaperTradeJournal
from strategy.levels_v2 import PriceZone, SUPPORT
from strategy.market_snapshot import MarketSnapshot
from strategy.paper import PaperTradingEngine
from strategy.paper_session import PaperSessionRunner
from strategy.realtime import LiveEvaluation
from strategy.realtime_guard import DataQuality
from strategy.realtime_supervisor import ALLOW, SupervisorDecision


def dt(minute: int) -> datetime:
    return datetime(2026, 1, 1, 0, minute, tzinfo=timezone.utc)


def zone() -> PriceZone:
    return PriceZone(low=99.0, high=100.0, kind=SUPPORT, touches=3)


def evaluation(minute: int, action: str = LONG) -> LiveEvaluation:
    candle = Candle(100.0, 103.0, 100.0, 102.0)
    signal = EngineSignal(action, "confirmed", "1m", zone=zone() if action == LONG else None)
    snapshot = MarketSnapshot(
        symbol="EURUSD",
        timeframe="1m",
        bar_time=dt(minute),
        candle=candle,
        current_close=102.0,
        data_quality=DataQuality(True, "ok", dt(minute), 0.0),
    )
    supervisor = SupervisorDecision(ALLOW, True, ("ok",)) if action == LONG else SupervisorDecision(WAIT, False, ("strategy is WAIT",))
    return LiveEvaluation(
        symbol="EURUSD",
        timeframe="1m",
        evaluated_at=dt(minute),
        bar_time=dt(minute),
        signal=signal,
        support=zone(),
        resistance=None,
        data_quality="ok",
        supervisor=supervisor,
        snapshot=snapshot,
    )


class FakeMonitor:
    def __init__(self, evaluations):
        self._evaluations = iter(evaluations)

    def evaluate_once(self, now=None):
        return next(self._evaluations, None)


def test_signal_from_bar_n_opens_on_bar_n_plus_1_only():
    runner = PaperSessionRunner(FakeMonitor([evaluation(1), evaluation(2)]))
    first = runner.process_once()
    assert first is not None
    assert first.opened is None
    assert runner.paper.position is None

    second = runner.process_once()
    assert second is not None
    assert second.opened is not None
    assert second.opened.signal_time == dt(1)
    assert second.opened.entry_time == dt(2)


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


def test_wait_does_not_create_pending_trade():
    runner = PaperSessionRunner(FakeMonitor([evaluation(1, WAIT)]))
    result = runner.process_once()
    assert result is not None
    assert runner.pending_signal is None
    assert runner.paper.position is None
