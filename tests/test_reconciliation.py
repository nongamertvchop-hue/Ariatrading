from datetime import datetime, timezone

import pytest

from live.reconciliation import ReconciliationError, reconcile_paper_state
from strategy.engine import EngineSignal, LONG
from strategy.journal import PaperTradeJournal
from strategy.levels_v2 import PriceZone, SUPPORT
from strategy.paper import PaperTradingEngine
from strategy.realtime import LiveEvaluation


def dt(minute: int) -> datetime:
    return datetime(2026, 1, 1, 0, minute, tzinfo=timezone.utc)


def signal():
    return EngineSignal(LONG, "confirmed", "1m", zone=PriceZone(99.0, 100.0, SUPPORT, 3))


def open_position():
    paper = PaperTradingEngine()
    position = paper.open_from_signal(signal(), signal_time=dt(1), entry_time=dt(2), entry_price=102.0)
    assert position is not None
    return paper, position


def pending_evaluation():
    return LiveEvaluation(
        symbol="EURUSD",
        timeframe="1m",
        evaluated_at=dt(1),
        bar_time=dt(1),
        signal=signal(),
        support=PriceZone(99.0, 100.0, SUPPORT, 3),
        resistance=None,
        snapshot=None,
        supervisor=None,
    )


def test_valid_open_position_and_journal_pass_reconciliation():
    paper, position = open_position()
    journal = PaperTradeJournal()
    journal.record_open(
        event_time=position.entry_time,
        symbol="EURUSD",
        timeframe="1m",
        position=position,
    )

    reconcile_paper_state(
        paper=paper,
        journal=journal,
        pending_signal=None,
        last_processed_bar_time=dt(2),
    )


def test_unmatched_open_without_position_fails():
    paper = PaperTradingEngine()
    source_paper, position = open_position()
    journal = PaperTradeJournal()
    journal.record_open(event_time=position.entry_time, symbol="EURUSD", timeframe="1m", position=position)

    with pytest.raises(ReconciliationError, match="OPEN_WITHOUT_POSITION"):
        reconcile_paper_state(
            paper=paper,
            journal=journal,
            pending_signal=None,
            last_processed_bar_time=dt(2),
        )


def test_position_without_journal_open_fails():
    paper, _ = open_position()

    with pytest.raises(ReconciliationError, match="POSITION_WITHOUT_OPEN"):
        reconcile_paper_state(
            paper=paper,
            journal=PaperTradeJournal(),
            pending_signal=None,
            last_processed_bar_time=dt(2),
        )


def test_pending_signal_with_open_position_fails():
    paper, position = open_position()
    journal = PaperTradeJournal()
    journal.record_open(event_time=position.entry_time, symbol="EURUSD", timeframe="1m", position=position)

    with pytest.raises(ReconciliationError, match="PENDING_WITH_OPEN_POSITION"):
        reconcile_paper_state(
            paper=paper,
            journal=journal,
            pending_signal=pending_evaluation(),
            last_processed_bar_time=dt(2),
        )


def test_closed_trade_counter_must_match_journal_closes():
    paper, position = open_position()
    journal = PaperTradeJournal()
    journal.record_open(event_time=position.entry_time, symbol="EURUSD", timeframe="1m", position=position)
    closed = position.__class__(
        **{
            **position.__dict__,
            "status": "CLOSED",
            "exit_time": dt(3),
            "exit_price": position.stop,
            "outcome": "LOSS",
            "r_multiple": -1.0,
            "bars_held": 1,
        }
    )
    journal.record_close(event_time=dt(3), symbol="EURUSD", timeframe="1m", position=closed)

    with pytest.raises(ReconciliationError, match="CLOSED_TRADE_COUNT_MISMATCH"):
        reconcile_paper_state(
            paper=paper,
            journal=journal,
            pending_signal=None,
            last_processed_bar_time=dt(3),
        )


def test_event_after_last_processed_bar_fails():
    paper = PaperTradingEngine()
    journal = PaperTradeJournal()
    journal.record_signal(
        event_time=dt(3),
        signal_time=dt(3),
        symbol="EURUSD",
        timeframe="1m",
        signal=signal(),
    )

    with pytest.raises(ReconciliationError, match="EVENT_AFTER_LAST_BAR"):
        reconcile_paper_state(
            paper=paper,
            journal=journal,
            pending_signal=None,
            last_processed_bar_time=dt(2),
        )
