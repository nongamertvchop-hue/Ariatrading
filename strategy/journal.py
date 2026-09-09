"""Structured journal for paper-trading research events.

The journal records observations and completed paper trades without performing
any broker interaction. Records are immutable and can be exported as plain
Python dictionaries for later analysis or persistence.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Iterable

from .engine import EngineSignal, LONG, SHORT, WAIT
from .paper import PaperPosition


@dataclass(frozen=True)
class JournalEvent:
    event_time: datetime
    event_type: str
    symbol: str
    timeframe: str
    action: str
    reason: str
    trade_id: int | None = None
    entry_price: float | None = None
    stop: float | None = None
    target: float | None = None
    exit_price: float | None = None
    outcome: str | None = None
    r_multiple: float | None = None
    bars_held: int | None = None
    signal_id: str | None = None

    def __post_init__(self) -> None:
        if self.event_time.tzinfo is None or self.event_time.utcoffset() is None:
            raise ValueError("event_time must be timezone-aware")
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if not self.timeframe:
            raise ValueError("timeframe must not be empty")
        if self.action not in {LONG, SHORT, WAIT}:
            raise ValueError("action must be LONG, SHORT, or WAIT")
        if self.trade_id is not None and self.trade_id < 1:
            raise ValueError("trade_id must be >= 1")
        for name, value in (("entry_price", self.entry_price), ("stop", self.stop), ("target", self.target), ("exit_price", self.exit_price), ("r_multiple", self.r_multiple)):
            if value is not None and not isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.bars_held is not None and self.bars_held < 0:
            raise ValueError("bars_held must be >= 0")

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["event_time"] = self.event_time.isoformat()
        return data


class PaperTradeJournal:
    """Append-only in-memory journal suitable for paper-session research."""

    def __init__(self) -> None:
        self._events: list[JournalEvent] = []

    @property
    def events(self) -> tuple[JournalEvent, ...]:
        return tuple(self._events)

    def record_signal(
        self,
        *,
        event_time: datetime,
        symbol: str,
        timeframe: str,
        signal: EngineSignal,
    ) -> JournalEvent:
        event = JournalEvent(
            event_time=event_time,
            event_type="SIGNAL",
            symbol=symbol,
            timeframe=timeframe,
            action=signal.action,
            reason=signal.reason,
            trade_id=None,
            signal_id=getattr(signal, "signal_id", None),
        )
        self._events.append(event)
        return event

    def record_open(
        self,
        *,
        event_time: datetime,
        symbol: str,
        timeframe: str,
        position: PaperPosition,
    ) -> JournalEvent:
        event = JournalEvent(
            event_time=event_time,
            event_type="OPEN",
            symbol=symbol,
            timeframe=timeframe,
            action=position.direction,
            reason="paper position opened",
            trade_id=position.trade_id,
            entry_price=position.entry_price,
            stop=position.stop,
            target=position.target,
        )
        self._events.append(event)
        return event

    def record_close(
        self,
        *,
        event_time: datetime,
        symbol: str,
        timeframe: str,
        position: PaperPosition,
    ) -> JournalEvent:
        if position.status != "CLOSED":
            raise ValueError("position must be CLOSED before journaling close")
        event = JournalEvent(
            event_time=event_time,
            event_type="CLOSE",
            symbol=symbol,
            timeframe=timeframe,
            action=position.direction,
            reason="paper position closed",
            trade_id=position.trade_id,
            entry_price=position.entry_price,
            stop=position.stop,
            target=position.target,
            exit_price=position.exit_price,
            outcome=position.outcome,
            r_multiple=position.r_multiple,
            bars_held=position.bars_held,
        )
        self._events.append(event)
        return event

    def as_dicts(self) -> list[dict[str, Any]]:
        return [event.as_dict() for event in self._events]

    def trade_events(self, trade_id: int) -> tuple[JournalEvent, ...]:
        return tuple(event for event in self._events if event.trade_id == trade_id)

    def signal_events(self, signal_id: str) -> tuple[JournalEvent, ...]:
        return tuple(event for event in self._events if event.signal_id == signal_id)
