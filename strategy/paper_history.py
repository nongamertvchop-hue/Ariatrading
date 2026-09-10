"""Append-only long-term paper runtime history.

History is intentionally local/durable and independent from the latest runtime
checkpoint. Each record links to the previous record with SHA-256, so edits,
reordering, truncation, or accidental corruption are detectable.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


class PaperHistoryError(RuntimeError):
    """Raised when paper history is unsafe to read or write."""


@dataclass(frozen=True)
class HistorySnapshot:
    sequence: int
    timestamp: str
    bar_time: str | None
    balance: float
    equity: float
    realized_pnl: float
    unrealized_pnl: float
    peak_equity: float
    drawdown: float
    drawdown_pct: float
    trade_count: int
    previous_hash: str
    record_hash: str


def _payload(record: dict) -> bytes:
    unsigned = dict(record)
    unsigned.pop("record_hash", None)
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _hash(record: dict) -> str:
    return hashlib.sha256(_payload(record)).hexdigest()


class PaperHistoryStore:
    """Durable JSONL history store for paper accounting snapshots."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def append(self, snapshot, *, bar_time: str | None = None) -> HistorySnapshot:
        events = self.verify()
        previous_hash = events[-1].record_hash if events else "GENESIS"
        record = {
            "sequence": len(events) + 1,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "bar_time": bar_time,
            "balance": float(snapshot.balance),
            "equity": float(snapshot.equity),
            "realized_pnl": float(snapshot.realized_pnl),
            "unrealized_pnl": float(snapshot.unrealized_pnl),
            "peak_equity": float(snapshot.peak_equity),
            "drawdown": float(snapshot.drawdown),
            "drawdown_pct": float(snapshot.drawdown_pct),
            "trade_count": int(snapshot.trade_count),
            "previous_hash": previous_hash,
        }
        record["record_hash"] = _hash(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            raise PaperHistoryError(f"failed to append paper history: {exc}") from exc
        return HistorySnapshot(**record)

    def verify(self) -> tuple[HistorySnapshot, ...]:
        if not self.path.exists():
            return ()
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise PaperHistoryError(f"failed to read paper history: {exc}") from exc
        previous_hash = "GENESIS"
        output: list[HistorySnapshot] = []
        for index, line in enumerate(lines, start=1):
            if not line.strip():
                raise PaperHistoryError(f"blank paper history line at {index}")
            try:
                raw = json.loads(line)
                event = HistorySnapshot(**raw)
            except (json.JSONDecodeError, TypeError, KeyError) as exc:
                raise PaperHistoryError(f"invalid paper history record at {index}") from exc
            if event.sequence != index:
                raise PaperHistoryError(f"paper history sequence break at {index}")
            if event.previous_hash != previous_hash:
                raise PaperHistoryError(f"paper history hash-chain break at {index}")
            if _hash(raw) != event.record_hash:
                raise PaperHistoryError(f"paper history record hash mismatch at {index}")
            previous_hash = event.record_hash
            output.append(event)
        return tuple(output)


__all__ = ["PaperHistoryError", "HistorySnapshot", "PaperHistoryStore"]
