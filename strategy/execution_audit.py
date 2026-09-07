"""Append-only audit journal for execution and recovery events.

The journal records execution state transitions without placing orders. Each
record contains the hash of the previous record, making accidental edits or
reordering detectable during verification.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


class AuditJournalError(RuntimeError):
    """Raised when an audit journal cannot be safely written or verified."""


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    timestamp: str
    event_type: str
    client_order_id: str
    state: str
    broker_order_id: str | None
    filled_quantity: float
    reason: str
    previous_hash: str
    event_hash: str


def _canonical_payload(event: dict) -> bytes:
    unsigned = dict(event)
    unsigned.pop("event_hash", None)
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _hash_event(event: dict) -> str:
    return hashlib.sha256(_canonical_payload(event)).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class AuditJournal:
    """Durable append-only JSONL audit journal with a SHA-256 hash chain."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def _last_hash(self) -> str:
        if not self.path.exists():
            return "GENESIS"
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise AuditJournalError(f"failed to read audit journal: {exc}") from exc
        if not lines:
            return "GENESIS"
        try:
            return str(json.loads(lines[-1])["event_hash"])
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise AuditJournalError("audit journal has an invalid final record") from exc

    def append(
        self,
        *,
        event_id: str,
        event_type: str,
        client_order_id: str,
        state: str,
        broker_order_id: str | None = None,
        filled_quantity: float = 0.0,
        reason: str = "",
    ) -> AuditEvent:
        if not event_id or not event_type or not client_order_id or not state:
            raise ValueError("event_id, event_type, client_order_id and state are required")
        if filled_quantity < 0:
            raise ValueError("filled_quantity must be >= 0")

        record = {
            "event_id": event_id,
            "timestamp": _now_iso(),
            "event_type": event_type,
            "client_order_id": client_order_id,
            "state": state,
            "broker_order_id": broker_order_id,
            "filled_quantity": float(filled_quantity),
            "reason": reason,
            "previous_hash": self._last_hash(),
        }
        record["event_hash"] = _hash_event(record)
        serialized = json.dumps(record, sort_keys=True, separators=(",", ":"))

        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(serialized + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            raise AuditJournalError(f"failed to append audit event: {exc}") from exc

        return AuditEvent(**record)

    def verify(self) -> tuple[AuditEvent, ...]:
        """Verify JSON validity, hash chain continuity, and event hashes."""
        if not self.path.exists():
            return ()
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise AuditJournalError(f"failed to read audit journal: {exc}") from exc

        expected_previous = "GENESIS"
        events: list[AuditEvent] = []
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                raise AuditJournalError(f"blank line in audit journal at line {line_number}")
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise TypeError
                event = AuditEvent(**record)
            except (json.JSONDecodeError, TypeError, KeyError) as exc:
                raise AuditJournalError(f"invalid audit record at line {line_number}") from exc

            if event.previous_hash != expected_previous:
                raise AuditJournalError(f"audit hash-chain break at line {line_number}")
            if _hash_event(record) != event.event_hash:
                raise AuditJournalError(f"audit event hash mismatch at line {line_number}")
            expected_previous = event.event_hash
            events.append(event)
        return tuple(events)
