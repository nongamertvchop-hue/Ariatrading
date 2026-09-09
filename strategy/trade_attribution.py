"""Read-only attribution queries over paper-trading journal events.

This module does not mutate the journal or trading engine. It reconstructs the
relationship between a canonical SIGNAL event and the paper trade lifecycle:
SIGNAL -> OPEN -> CLOSE.

The query layer is intentionally tolerant of legacy records that do not carry
a signal identity. Such records remain queryable by trade_id but are reported
as unattributed rather than guessed from timestamps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .journal import JournalEvent, PaperTradeJournal


@dataclass(frozen=True)
class TradeAttribution:
    """One paper trade with its source signal and lifecycle events."""

    trade_id: int
    signal: JournalEvent | None
    open_event: JournalEvent | None
    close_event: JournalEvent | None

    @property
    def signal_event_id(self) -> str | None:
        """Canonical signal identity, when the trade can be attributed."""
        if self.signal is not None:
            return self.signal.event_id
        if self.open_event is not None:
            return self.open_event.signal_event_id
        if self.close_event is not None:
            return self.close_event.signal_event_id
        return None

    @property
    def is_closed(self) -> bool:
        return self.close_event is not None

    @property
    def outcome(self) -> str | None:
        return self.close_event.outcome if self.close_event is not None else None

    @property
    def r_multiple(self) -> float | None:
        return self.close_event.r_multiple if self.close_event is not None else None


class PaperTradeAttribution:
    """Build deterministic, read-only trade-to-signal relationships."""

    def __init__(self, journal: PaperTradeJournal | Iterable[JournalEvent]) -> None:
        self._events = tuple(journal.events if isinstance(journal, PaperTradeJournal) else journal)
        self._by_trade: dict[int, list[JournalEvent]] = {}
        self._signal_by_id: dict[str, JournalEvent] = {}
        self._index()

    def _index(self) -> None:
        for event in self._events:
            if event.event_type == "SIGNAL":
                if event.event_id is not None:
                    previous = self._signal_by_id.get(event.event_id)
                    if previous is not None and previous != event:
                        raise ValueError(f"conflicting SIGNAL records for event_id: {event.event_id}")
                    self._signal_by_id[event.event_id] = event
            elif event.trade_id is not None:
                self._by_trade.setdefault(event.trade_id, []).append(event)

    def for_trade(self, trade_id: int) -> TradeAttribution | None:
        """Return attribution for one trade ID, or ``None`` when unknown."""
        if trade_id < 1:
            raise ValueError("trade_id must be >= 1")
        events = self._by_trade.get(trade_id)
        if not events:
            return None

        open_events = [event for event in events if event.event_type == "OPEN"]
        close_events = [event for event in events if event.event_type == "CLOSE"]
        if len(open_events) > 1:
            raise ValueError(f"multiple OPEN records for trade_id: {trade_id}")
        if len(close_events) > 1:
            raise ValueError(f"multiple CLOSE records for trade_id: {trade_id}")

        open_event = open_events[0] if open_events else None
        close_event = close_events[0] if close_events else None
        candidate_ids = {
            event.signal_event_id
            for event in (open_event, close_event)
            if event is not None and event.signal_event_id is not None
        }
        if len(candidate_ids) > 1:
            raise ValueError(f"conflicting signal_event_id for trade_id: {trade_id}")

        signal_id = next(iter(candidate_ids), None)
        signal = self._signal_by_id.get(signal_id) if signal_id is not None else None
        return TradeAttribution(
            trade_id=trade_id,
            signal=signal,
            open_event=open_event,
            close_event=close_event,
        )

    def by_signal_event_id(self, signal_event_id: str) -> tuple[TradeAttribution, ...]:
        """Return all paper trades attributed to one canonical signal."""
        if not signal_event_id:
            raise ValueError("signal_event_id must not be empty")
        matches: list[TradeAttribution] = []
        for trade_id in sorted(self._by_trade):
            attribution = self.for_trade(trade_id)
            if attribution is not None and attribution.signal_event_id == signal_event_id:
                matches.append(attribution)
        return tuple(matches)

    def all_trades(self, *, closed_only: bool = False) -> tuple[TradeAttribution, ...]:
        """Return all indexed paper trades in stable trade-ID order."""
        results = tuple(self.for_trade(trade_id) for trade_id in sorted(self._by_trade))
        filtered = tuple(result for result in results if result is not None)
        if closed_only:
            return tuple(result for result in filtered if result.is_closed)
        return filtered

    def unattributed_trades(self, *, closed_only: bool = False) -> tuple[TradeAttribution, ...]:
        """Return trades with no resolvable canonical signal identity."""
        results = self.all_trades(closed_only=closed_only)
        return tuple(result for result in results if result.signal_event_id is None or result.signal is None)

    def closed_outcomes(self) -> tuple[tuple[str, float | None], ...]:
        """Return ``(outcome, r_multiple)`` pairs for closed attributed/unattributed trades."""
        return tuple(
            (result.outcome, result.r_multiple)
            for result in self.all_trades(closed_only=True)
        )
