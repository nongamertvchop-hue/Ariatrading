"""Cross-check persisted paper state before a runtime resumes.

Checkpoint schema validation proves individual objects are well formed. This
module validates the relationships between the paper engine, journal, pending
signal, and last processed candle so a restart cannot resume from a silently
inconsistent state.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isclose
from typing import Any

from strategy.engine import LONG, SHORT
from strategy.journal import PaperTradeJournal
from strategy.paper import PaperTradingEngine
from strategy.realtime import LiveEvaluation


@dataclass(frozen=True)
class ReconciliationIssue:
    code: str
    message: str


class ReconciliationError(ValueError):
    """Raised when restored runtime components disagree about lifecycle state."""

    def __init__(self, issue: ReconciliationIssue) -> None:
        self.issue = issue
        super().__init__(f"{issue.code}: {issue.message}")


def reconcile_paper_state(
    *,
    paper: PaperTradingEngine,
    journal: PaperTradeJournal,
    pending_signal: LiveEvaluation | None,
    last_processed_bar_time: datetime | None,
) -> None:
    """Fail closed when persisted paper/journal state is internally inconsistent."""
    if last_processed_bar_time is not None:
        _aware_utc(last_processed_bar_time, "last_processed_bar_time")

    if pending_signal is not None:
        if pending_signal.signal.action not in {LONG, SHORT}:
            _fail("PENDING_NOT_DIRECTIONAL", "pending signal must be directional")
        if last_processed_bar_time is not None and pending_signal.bar_time > last_processed_bar_time:
            _fail("PENDING_AFTER_LAST_BAR", "pending signal cannot be newer than last processed bar")
        if paper.position is not None:
            _fail("PENDING_WITH_OPEN_POSITION", "pending signal cannot coexist with an open position")

    events = journal.events
    opens: dict[int, list[Any]] = {}
    closes: dict[int, list[Any]] = {}
    for event in events:
        if last_processed_bar_time is not None and event.event_time > last_processed_bar_time:
            _fail("EVENT_AFTER_LAST_BAR", "journal event is newer than last processed bar")
        if event.event_type == "OPEN":
            if event.trade_id is None:
                _fail("OPEN_WITHOUT_TRADE_ID", "OPEN event must have a trade_id")
            opens.setdefault(event.trade_id, []).append(event)
        elif event.event_type == "CLOSE":
            if event.trade_id is None:
                _fail("CLOSE_WITHOUT_TRADE_ID", "CLOSE event must have a trade_id")
            closes.setdefault(event.trade_id, []).append(event)

    for trade_id, trade_opens in opens.items():
        if len(trade_opens) != 1:
            _fail("DUPLICATE_OPEN", f"trade {trade_id} has {len(trade_opens)} OPEN events")
    for trade_id, trade_closes in closes.items():
        if len(trade_closes) != 1:
            _fail("DUPLICATE_CLOSE", f"trade {trade_id} has {len(trade_closes)} CLOSE events")
        if trade_id not in opens:
            _fail("CLOSE_WITHOUT_OPEN", f"trade {trade_id} has a CLOSE without an OPEN")

    for trade_id, trade_closes in closes.items():
        opening = opens[trade_id][0]
        closing = trade_closes[0]
        if closing.event_time < opening.event_time:
            _fail("CLOSE_BEFORE_OPEN", f"trade {trade_id} closes before it opens")
        if closing.action != opening.action:
            _fail("CLOSE_DIRECTION_MISMATCH", f"trade {trade_id} CLOSE direction does not match OPEN")
        if closing.entry_price != opening.entry_price:
            _fail("CLOSE_ENTRY_PRICE_MISMATCH", f"trade {trade_id} CLOSE entry_price does not match OPEN")
        if closing.stop != opening.stop or closing.target != opening.target:
            _fail("CLOSE_RISK_LEVEL_MISMATCH", f"trade {trade_id} CLOSE risk levels do not match OPEN")
        if closing.outcome not in {"WIN", "LOSS"}:
            _fail("CLOSE_OUTCOME_INVALID", f"trade {trade_id} CLOSE outcome must be WIN or LOSS")
        if closing.exit_price is None or closing.r_multiple is None or closing.bars_held is None:
            _fail("CLOSE_METADATA_MISSING", f"trade {trade_id} CLOSE is missing exit metadata")

    account = paper.account
    if account.closed_trades != len(closes):
        _fail(
            "CLOSED_TRADE_COUNT_MISMATCH",
            f"paper closed_trades={account.closed_trades} but journal CLOSE count={len(closes)}",
        )

    close_wins = sum(event.outcome == "WIN" for event in (items[0] for items in closes.values()))
    close_losses = sum(event.outcome == "LOSS" for event in (items[0] for items in closes.values()))
    if account.wins != close_wins or account.losses != close_losses:
        _fail(
            "WIN_LOSS_COUNT_MISMATCH",
            f"paper wins/losses={account.wins}/{account.losses} but journal={close_wins}/{close_losses}",
        )

    journal_realized_r = sum(float(event.r_multiple) for event in (items[0] for items in closes.values()))
    if not isclose(account.realized_r, journal_realized_r, rel_tol=1e-12, abs_tol=1e-12):
        _fail(
            "REALIZED_R_MISMATCH",
            f"paper realized_r={account.realized_r} but journal sum={journal_realized_r}",
        )
    if not isclose(account.balance, account.initial_balance + account.realized_r, rel_tol=1e-12, abs_tol=1e-12):
        _fail("BALANCE_MISMATCH", "paper balance is inconsistent with initial_balance + realized_r")

    position = paper.position
    unmatched_opens = {trade_id: items[0] for trade_id, items in opens.items() if trade_id not in closes}
    all_trade_ids = set(opens) | set(closes)
    if all_trade_ids:
        next_trade_id = paper.to_state().get("next_trade_id")
        if not isinstance(next_trade_id, int) or next_trade_id <= max(all_trade_ids):
            _fail("NEXT_TRADE_ID_NOT_MONOTONIC", "next_trade_id must be greater than every journal trade_id")

    if position is None:
        if unmatched_opens:
            trade_id = next(iter(unmatched_opens))
            _fail("OPEN_WITHOUT_POSITION", f"trade {trade_id} has an unmatched OPEN but no paper position")
    else:
        if position.trade_id not in unmatched_opens:
            _fail("POSITION_WITHOUT_OPEN", f"paper position trade {position.trade_id} has no unmatched OPEN")
        if len(unmatched_opens) != 1:
            _fail("MULTIPLE_OPEN_POSITIONS", "journal contains more than one unmatched OPEN")
        opening = unmatched_opens[position.trade_id]
        if opening.action != position.direction:
            _fail("POSITION_DIRECTION_MISMATCH", "journal OPEN direction does not match paper position")
        for field in ("entry_price", "stop", "target"):
            if getattr(opening, field) != getattr(position, field):
                _fail("POSITION_PRICE_MISMATCH", f"journal OPEN {field} does not match paper position")
        if opening.event_time != position.entry_time:
            _fail("POSITION_ENTRY_TIME_MISMATCH", "journal OPEN time does not match paper position entry_time")


def _aware_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ReconciliationError(
            ReconciliationIssue("NAIVE_TIMESTAMP", f"{field_name} must be timezone-aware")
        )
    return value.astimezone(timezone.utc)


def _fail(code: str, message: str) -> None:
    raise ReconciliationError(ReconciliationIssue(code, message))


__all__ = ["ReconciliationIssue", "ReconciliationError", "reconcile_paper_state"]
