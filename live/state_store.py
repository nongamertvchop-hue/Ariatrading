"""Durable local checkpoint storage for the paper runtime.

The store is deliberately small and backend-neutral at the runtime boundary:
JSON is sufficient for the current single-process research/paper phase. Writes
use a temporary file followed by ``os.replace`` so a process crash cannot leave
half-written JSON at the target path.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class JsonRuntimeStateStore:
    """Atomically persist and load a JSON-serializable runtime checkpoint."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def save(self, state: dict[str, Any]) -> None:
        if not isinstance(state, dict):
            raise ValueError("runtime state must be a dictionary")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=self.path.parent,
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(state, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise

    def load(self) -> dict[str, Any]:
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                state = json.load(handle)
        except FileNotFoundError:
            raise
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"failed to load runtime checkpoint: {self.path}") from exc
        if not isinstance(state, dict):
            raise ValueError("runtime checkpoint root must be a dictionary")
        return state

    def exists(self) -> bool:
        return self.path.is_file()
