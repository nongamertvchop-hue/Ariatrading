"""Atomic runtime observability snapshot for operators and dashboards."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RuntimeStatusStore:
    """Persist the latest runtime heartbeat without exposing broker credentials."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def write(self, **fields: Any) -> None:
        payload = dict(fields)
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True, default=str)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        except OSError as exc:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise RuntimeError(f"runtime status cannot be persisted safely: {exc}") from exc

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"runtime status unreadable: {exc}") from exc
        if not isinstance(value, dict):
            raise RuntimeError("runtime status must be an object")
        return value
