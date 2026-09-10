"""Crash-safe checkpoint persistence for the continuous paper runtime."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile


class PaperCheckpointError(RuntimeError):
    """Raised when a runtime checkpoint cannot be trusted."""


def save_checkpoint(payload: dict, path: str | os.PathLike[str]) -> None:
    if not isinstance(payload, dict):
        raise PaperCheckpointError("checkpoint payload must be an object")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    temp_name: str | None = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False) as handle:
            temp_name = handle.name
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    except OSError as exc:
        if temp_name is not None:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass
        raise PaperCheckpointError(f"failed to save paper runtime checkpoint: {exc}") from exc


def load_checkpoint(path: str | os.PathLike[str]) -> dict:
    target = Path(path)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PaperCheckpointError(f"failed to load paper runtime checkpoint: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise PaperCheckpointError("unsupported or malformed paper runtime checkpoint")
    return payload


__all__ = ["PaperCheckpointError", "save_checkpoint", "load_checkpoint"]
