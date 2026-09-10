"""Small dependency-free runtime telemetry for operator visibility.

The telemetry layer is intentionally append-only for events and atomic for the
latest heartbeat. It never authorizes an order; it only records runtime state.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RuntimeTelemetry:
    def __init__(self, heartbeat_path: str | Path, events_path: str | Path) -> None:
        self.heartbeat_path = Path(heartbeat_path)
        self.events_path = Path(events_path)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def heartbeat(self, *, status: str, mode: str, account: int | None = None, processed: int = 0, reason: str = "") -> None:
        payload: dict[str, Any] = {
            "timestamp": self._now(),
            "status": str(status),
            "mode": str(mode),
            "account": account,
            "processed": int(processed),
            "reason": str(reason),
        }
        self.heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{self.heartbeat_path.name}.", dir=self.heartbeat_path.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.heartbeat_path)
        except OSError:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def event(self, event_type: str, **fields: Any) -> None:
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"timestamp": self._now(), "event": str(event_type), **fields}
        with self.events_path.open("a", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
