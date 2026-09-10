"""Fail-closed idempotency journal for the demo execution boundary.

The journal solves a subtle failure mode: a broker request can time out after the
broker accepted it. Retrying immediately can create a duplicate position. An
intent therefore has an explicit AMBIGUOUS state, and ambiguous intents are
never automatically retried.

This module is deliberately independent of the strategy layer and contains no
broker API calls. It is safe to use for ALERT_ONLY/DEMO orchestration only.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TERMINAL_STATES = frozenset({"SUCCEEDED", "FAILED"})
NON_RETRYABLE_STATES = frozenset({"AMBIGUOUS"})


@dataclass(frozen=True)
class ExecutionIntent:
    """Immutable identity and request data for one execution attempt."""

    intent_id: str
    symbol: str
    direction: str
    bar_time: str
    entry: float
    sl: float
    tp: float | None
    lot_size: float


def build_intent(
    *,
    symbol: str,
    direction: str,
    bar_time: datetime,
    entry: float,
    sl: float,
    tp: float | None,
    lot_size: float,
) -> ExecutionIntent:
    """Build a deterministic idempotency key from the execution intent."""
    payload = {
        "symbol": symbol.strip().upper(),
        "direction": direction.strip().upper(),
        "bar_time": bar_time.astimezone(timezone.utc).isoformat(),
        "entry": float(entry),
        "sl": float(sl),
        "tp": None if tp is None else float(tp),
        "lot_size": float(lot_size),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    intent_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return ExecutionIntent(intent_id=intent_id, **payload)


class ExecutionJournal:
    """Small durable JSON journal with atomic replacement and fail-closed states."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Execution journal cannot be read safely: {exc}") from exc
        if not isinstance(raw, dict):
            raise RuntimeError("Execution journal has invalid root type")
        return raw

    def _save(self, records: dict[str, dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(records, handle, sort_keys=True, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        except OSError as exc:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise RuntimeError(f"Execution journal cannot be persisted safely: {exc}") from exc

    def get(self, intent_id: str) -> dict[str, Any] | None:
        return self._load().get(intent_id)

    def reserve(self, intent: ExecutionIntent) -> bool:
        """Reserve an intent once. False means it already exists and must not repeat."""
        records = self._load()
        if intent.intent_id in records:
            return False
        records[intent.intent_id] = {
            **asdict(intent),
            "state": "RESERVED",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save(records)
        return True

    def transition(self, intent_id: str, state: str, **metadata: Any) -> None:
        """Move an intent to a valid state without silently reopening terminal/ambiguous work."""
        allowed = {"RESERVED", "SUBMITTED", "SUCCEEDED", "FAILED", "AMBIGUOUS"}
        if state not in allowed:
            raise ValueError(f"Unsupported execution state: {state}")
        records = self._load()
        record = records.get(intent_id)
        if record is None:
            raise KeyError(f"Unknown execution intent: {intent_id}")
        current = str(record.get("state"))
        if current in TERMINAL_STATES or current in NON_RETRYABLE_STATES:
            if state != current:
                raise RuntimeError(f"Cannot transition {current} intent {intent_id}")
            return
        if current == "RESERVED" and state not in {"RESERVED", "SUBMITTED", "SUCCEEDED", "FAILED", "AMBIGUOUS"}:
            raise RuntimeError(f"Invalid transition {current} -> {state}")
        if current == "SUBMITTED" and state not in {"SUBMITTED", "SUCCEEDED", "FAILED", "AMBIGUOUS"}:
            raise RuntimeError(f"Invalid transition {current} -> {state}")
        record.update(metadata)
        record["state"] = state
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save(records)

    def recoverable_intents(self) -> list[dict[str, Any]]:
        """Return only intents that require reconciliation, never automatic duplicate submission."""
        records = self._load()
        return [
            record
            for record in records.values()
            if record.get("state") in {"RESERVED", "SUBMITTED", "AMBIGUOUS"}
        ]
