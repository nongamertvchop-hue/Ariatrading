"""Persistent control state for the Ariatrading runtime."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

RUN = "RUN"
PAUSE = "PAUSE"
STOP = "STOP"
EMERGENCY_STOP = "EMERGENCY_STOP"
_ALLOWED = {RUN, PAUSE, STOP, EMERGENCY_STOP}


@dataclass(frozen=True)
class BotControlState:
    state: str
    updated_at: str
    reason: str
    generation: int


class BotControlPlane:
    """Atomic JSON-backed operator control with restart-safe state."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = Lock()

    def _default(self) -> BotControlState:
        return BotControlState(
            STOP, datetime.now(timezone.utc).isoformat(), "initial state", 0
        )

    def _read_unlocked(self) -> BotControlState:
        if not self.path.exists():
            return self._default()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"bot control state unreadable: {exc}") from exc
        if not isinstance(raw, dict):
            raise RuntimeError("bot control state must be an object")
        state = str(raw.get("state", STOP)).upper()
        if state not in _ALLOWED:
            raise RuntimeError(f"invalid bot control state: {state}")
        try:
            generation = int(raw.get("generation", 0))
        except (TypeError, ValueError) as exc:
            raise RuntimeError("bot control generation must be an integer") from exc
        if generation < 0:
            raise RuntimeError("bot control generation must be non-negative")
        return BotControlState(
            state=state,
            updated_at=str(raw.get("updated_at", "")),
            reason=str(raw.get("reason", "")),
            generation=generation,
        )

    def read(self) -> BotControlState:
        with self._lock:
            return self._read_unlocked()

    def set(self, state: str, reason: str = "operator request") -> BotControlState:
        state = state.upper().strip()
        if state not in _ALLOWED:
            raise ValueError(f"unsupported bot state: {state}")
        with self._lock:
            current = self._read_unlocked()
            next_state = BotControlState(
                state,
                datetime.now(timezone.utc).isoformat(),
                reason,
                current.generation + 1,
            )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                prefix=self.path.name + ".", dir=self.path.parent
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(asdict(next_state), handle, indent=2, sort_keys=True)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp_name, self.path)
            finally:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
            return next_state

    def can_trade(self) -> bool:
        return self.read().state == RUN
