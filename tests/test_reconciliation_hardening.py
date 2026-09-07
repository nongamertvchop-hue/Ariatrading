from dataclasses import replace
from datetime import datetime, timezone

import pytest

from live.reconciliation import ReconciliationError, reconcile_paper_state
from strategy.engine import EngineSignal, LONG
from strategy.journal import PaperTradeJournal
from strategy.levels_v2 import PriceZone, SUPPORT
from strategy.paper import CLOSED, PaperTradingEngine


def dt(minute: int) -> datetime:
    return datetime(2026, 1, 1, 0, minute, tzinfo=timezone.utc)


def signal():
    return EngineSignal(LONG, "confirmed", "1m", zone=PriceZone(99.0, 100.0, SUPPORT, 3))


def closed_trade():
    paper = PaperTradingEngine()
    position = paper.open_from_signal(signal(), signal_time=dt(1), entry_time=dt(2), entry_price=102.0)
    assert position is not None
    closed = paper.on_bar({"time": dt(3), "high": position.stop, "low": position.stop})
    assert closed is not None
    assert closed.status == CLOSED
    return paper, closed


def opened_version(position):
    return replace(
        position,
        status="OPEN",
        outcome="OPEN",
        exit_time=None,
        exit_price=None,
        r_multiple=0.0,
        bars_held=0,
    )


def test_reconciliation_rejects_win_loss_counter_mismatch():
    paper, closed = closed_trade()
    journal = PaperTradeJournal()
    journal.record_open(event_time=closed.entry_time, symbol="EURUSD", timeframe="1m", position=opened_version(closed))
    journal.record_close(
        event_time=closed.exit_time,
        symbol="EURUSD",
        timeframe="1m",
        position=replace(closed, outcome="WIN"),
    )

    with pytest.raises(ReconciliationError, match="WIN_LOSS_COUNT_MISMATCH"):
        reconcile_paper_state(
            paper=paper,
            journal=journal,
            pending_signal=None,
            last_processed_bar_time=dt(3),
        )


def test_reconciliation_rejects_realized_r_mismatch():
    paper, closed = closed_trade()
    journal = PaperTradeJournal()
    journal.record_open(event_time=closed.entry_time, symbol="EURUSD", timeframe="1m", position=opened_version(closed))
    journal.record_close(
        event_time=closed.exit_time,
        symbol="EURUSD",
        timeframe="1m",
        position=replace(closed, r_multiple=closed.r_multiple + 0.5),
    )

    with pytest.raises(ReconciliationError, match="REALIZED_R_MISMATCH"):
        reconcile_paper_state(
            paper=paper,
            journal=journal,
            pending_signal=None,
            last_processed_bar_time=dt(3),
        )


def test_reconciliation_rejects_next_trade_id_not_ahead_of_journal():
    paper, first_closed = closed_trade()
    journal = PaperTradeJournal()

    first_open = opened_version(first_closed)
    journal.record_open(
        event_time=first_open.entry_time,
        symbol="EURUSD",
        timeframe="1m",
        position=replace(first_open, trade_id=99),
    )
    journal.record_close(
        event_time=first_closed.exit_time,
        symbol="EURUSD",
        timeframe="1m",
        position=replace(first_closed, trade_id=99),
    )

    second = paper.open_from_signal(
        signal(),
        signal_time=dt(3),
        entry_time=dt(4),
        entry_price=103.0,
    )
    assert second is not None
    journal.record_open(
        event_time=second.entry_time,
        symbol="EURUSD",
        timeframe="1m",
        position=second,
    )

    with pytest.raises(ReconciliationError, match="NEXT_TRADE_ID_NOT_MONOTONIC"):
        reconcile_paper_state(
            paper=paper,
            journal=journal,
            pending_signal=None,
            last_processed_bar_time=dt(4),
        )
