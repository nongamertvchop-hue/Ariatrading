"""Durable, human-attested evidence for DEMO soak and staged LIVE release."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class EvidenceRecord:
    item: int
    passed: bool
    observed_at: str
    reference: str
    notes: str = ""

    @staticmethod
    def create(item: int, passed: bool, reference: str, notes: str = "") -> "EvidenceRecord":
        if item < 1 or item > 50:
            raise ValueError("readiness item must be between 1 and 50")
        if not reference.strip():
            raise ValueError("evidence reference is required")
        return EvidenceRecord(item, bool(passed), datetime.now(timezone.utc).isoformat(), reference.strip(), notes.strip())


def load_evidence(path: str | Path) -> list[EvidenceRecord]:
    target = Path(path)
    if not target.exists():
        return []
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"release evidence cannot be read safely: {exc}") from exc
    if not isinstance(raw, list):
        raise RuntimeError("release evidence root must be a list")
    return [EvidenceRecord(**entry) for entry in raw]


def save_evidence(path: str | Path, records: list[EvidenceRecord]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump([asdict(record) for record in records], handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except OSError as exc:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise RuntimeError(f"release evidence cannot be persisted safely: {exc}") from exc


def build_readiness_map(records: list[EvidenceRecord]) -> dict[int, bool]:
    """Latest explicit record wins; absent items remain unproven."""
    result: dict[int, bool] = {}
    for record in records:
        result[record.item] = record.passed
    return result
