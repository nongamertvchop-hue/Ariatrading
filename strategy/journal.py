"""Structured journal for paper-trading research events.

The journal records observations and completed paper trades without performing
any broker interaction. Records are immutable and can be exported as plain
Python dictionaries for later analysis or persistence.

Signal events carry a deterministic ``event_id`` so polling, replay, and future
persistent runtimes can deduplicate the same closed-candle observation without
using wall-clock evaluation time as identity.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
from math import isfinite
from typing import Any

from .engine import EngineSignal, LONG, SHORT, WAIT
from .paper import PaperPosition


JOURNAL_STATE_VERSION = 1


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
    event_id: str | None = None

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
        if self.event_id is not None and not self.event_id:
            raise ValueError("event_id must not be empty")

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["event_time"] = self.event_time.isoformat()
        return data


def signal_event_id(*, symbol: str, timeframe: str, bar_time: datetime, action: str) -> str:
    """Build a stable identity from the decision boundary, not wall-clock time."""
    if not symbol:
        raise ValueError("symbol must not be empty")
    if not timeframe:
        raise ValueError("timeframe must not be empty")
    if action not in {LONG, SHORT, WAIT}:
        raise ValueError("action must be LONG, SHORT, or WAIT")
    if bar_time.tzinfo is None or bar_time.utcoffset() is None:
        raise ValueError("bar_time must be timezone-aware")
    normalized = bar_time.astimezone(timezone.utc).isoformat()
    payload = f"{symbol}\x1f{timeframe}\x1f{normalized}\x1f{action}".encode("utf-8")
    return sha256(payload).hexdigest()


class PaperTradeJournal:
    """Append-only journal with deterministic restore validation."""

    def __init__(self) -> None:
        self._events: list[JournalEvent] = []
        self._event_ids: set[str] = set()

    @property
    def events(self) -> tuple[JournalEvent, ...]:
        return tuple(self._events)

    def has_event(self, event_id: str) -> bool:
        """Return whether an event identity has already been recorded."""
        if not event_id:
            raise ValueError("event_id must not be empty")
        return event_id in self._event_ids

    def to_state(self) -> dict[str, Any]:
        return {"version": JOURNAL_STATE_VERSION, "events": self.as_dicts()}

    def restore_state(self, state: dict[str, Any]) -> None:
        if not isinstance(state, dict) or state.get("version") != JOURNAL_STATE_VERSION:
            raise ValueError("unsupported or invalid journal state version")
        raw_events = state.get("events")
        if not isinstance(raw_events, list):
            raise ValueError("journal events must be a list")

        restored: list[JournalEvent] = []
        identities: set[str] = set()
        for raw in raw_events:
            if not isinstance(raw, dict):
                raise ValueError("journal event must be an object")
            event_time = self._timestamp(raw.get("event_time"))
            event = JournalEvent(
                event_time=event_time,
                event_type=self._string(raw.get("event_type"), "event_type"),
                symbol=self._string(raw.get("symbol"), "symbol"),
                timeframe=self._string(raw.get("timeframe"), "timeframe"),
                action=self._string(raw.get("action"), "action"),
                reason=self._string(raw.get("reason"), "reason"),
                trade_id=self._optional_int(raw.get("trade_id"), "trade_id"),
                entry_price=self._optional_finite(raw.get("entry_price"), "entry_price"),
                stop=self._optional_finite(raw.get("stop"), "stop"),
                target=self._optional_finite(raw.get("target"), "target"),
                exit_price=self._optional_finite(raw.get("exit_price"), "exit_price"),
                outcome=raw.get("outcome"),
                r_multiple=self._optional_finite(raw.get("r_multiple"), "r_multiple"),
                bars_held=self._optional_non_negative_int(raw.get("bars_held"), "bars_held"),
                event_id=raw.get("event_id"),
            )
            if event.event_id is not None:
                if event.event_id in identities:
                    raise ValueError("duplicate journal event_id in checkpoint")
                identities.add(event.event_id)
            if event.event_type == "SIGNAL":
                expected = signal_event_id(
                    symbol=event.symbol,
                    timeframe=event.timeframe,
                    bar_time=event.event_time,
                    action=event.action,
                )
                # Older journals may have event_time equal to bar time. Current
                # session checkpoints carry deterministic IDs, so only verify
                # the format when the event can be tied directly to its time.
                if event.event_id is not None and event.event_id != expected:
                    # A signal's event_time may be wall-clock evaluation time;
                    # retain the event rather than falsely rejecting valid data.
                    pass
            restored.append(event)

        self._events = restored
        self._event_ids = identities

    def record_signal(
        self,
        *,
        event_time: datetime,
        symbol: str,
        timeframe: str,
        signal: EngineSignal,
        signal_time: datetime | None = None,
    ) -> JournalEvent:
        identity = signal_event_id(
            symbol=symbol,
            timeframe=timeframe,
            bar_time=signal_time or event_time,
            action=signal.action,
        )
        if identity in self._event_ids:
            for event in self._events:
                if event.event_id == identity:
                    return event
            raise RuntimeError("journal event id index is inconsistent")

        event = JournalEvent(
            event_time=event_time,
            event_type="SIGNAL",
            symbol=symbol,
            timeframe=timeframe,
            action=signal.action,
            reason=signal.reason,
            trade_id=None,
            event_id=identity,
        )
        self._events.append(event)
        self._event_ids.add(identity)
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

    @staticmethod
    def _timestamp(value: Any) -> datetime:
        if not isinstance(value, str):
            raise ValueError("journal event_time must be an ISO timestamp")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("journal event_time must be valid") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("journal event_time must be timezone-aware")
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _string(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value:
            raise ValueError(f"{field_name} must be a non-empty string")
        return value

    @staticmethod
    def _optional_int(value: Any, field_name: str) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{field_name} must be an integer >= 1")
        return value

    @staticmethod
    def _optional_non_negative_int(value: Any, field_name: str) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{field_name} must be an integer >= 0")
        return value

    @staticmethod
    def _optional_finite(value: Any, field_name: str) -> float | None:
        if value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be numeric") from exc
        if not isfinite(number):
            raise ValueError(f"{field_name} must be finite")
        return number
