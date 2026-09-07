"""Crash-safe checkpoints for the automatic paper runtime.

The checkpoint deliberately stores only orchestration state. It is not a broker
ledger. A checkpoint that indicates an open paper position is rejected on
restore until full account/position persistence exists, because silently
restarting a position-less simulator would corrupt the research record.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from strategy.engine import EngineSignal, LONG, SHORT
from strategy.levels_v2 import PriceZone, RESISTANCE, SUPPORT


class PaperCheckpointError(RuntimeError):
    """Raised when a paper-runtime checkpoint is unsafe or malformed."""


@dataclass(frozen=True)
class PendingSignalState:
    symbol: str
    timeframe: str
    bar_time: datetime
    signal: EngineSignal


@dataclass(frozen=True)
class PaperRuntimeCheckpoint:
    last_bar_time: datetime | None
    pending_signal: PendingSignalState | None
    position_open: bool
    version: int = 1


def _timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise PaperCheckpointError("checkpoint timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _parse_timestamp(value: object, field: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PaperCheckpointError(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise PaperCheckpointError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PaperCheckpointError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _signal_to_dict(state: PendingSignalState) -> dict:
    signal = state.signal
    zone = signal.zone
    if zone is None:
        raise PaperCheckpointError("pending directional signal must include a zone")
    score = signal.score
    score_payload = None
    if score is not None:
        score_payload = {
            key: value
            for key, value in score.__dict__.items()
            if isinstance(value, (str, int, float, bool)) or value is None
        }
    return {
        "symbol": state.symbol,
        "timeframe": state.timeframe,
        "bar_time": _timestamp(state.bar_time),
        "signal": {
            "action": signal.action,
            "reason": signal.reason,
            "timeframe": signal.timeframe,
            "zone": {
                "low": zone.low,
                "high": zone.high,
                "kind": zone.kind,
                "touches": zone.touches,
            },
            "protection": signal.protection,
            "breakout_state": signal.breakout_state,
            "entry_reference": signal.entry_reference,
            "stop_reference": signal.stop_reference,
            "test_index": signal.test_index,
            "confirmation_index": signal.confirmation_index,
            "structure_bias": signal.structure_bias,
            "score": score_payload,
        },
    }


def _signal_from_dict(raw: object) -> PendingSignalState:
    if not isinstance(raw, dict):
        raise PaperCheckpointError("pending signal must be an object")
    symbol = raw.get("symbol")
    timeframe = raw.get("timeframe")
    bar_time = _parse_timestamp(raw.get("bar_time"), "pending bar_time")
    payload = raw.get("signal")
    if not isinstance(symbol, str) or not symbol:
        raise PaperCheckpointError("pending symbol is invalid")
    if not isinstance(timeframe, str) or not timeframe:
        raise PaperCheckpointError("pending timeframe is invalid")
    if bar_time is None or not isinstance(payload, dict):
        raise PaperCheckpointError("pending signal is incomplete")

    action = payload.get("action")
    if action not in {LONG, SHORT}:
        raise PaperCheckpointError("pending signal action must be LONG or SHORT")
    zone_raw = payload.get("zone")
    if not isinstance(zone_raw, dict):
        raise PaperCheckpointError("pending signal zone is missing")
    try:
        zone = PriceZone(
            float(zone_raw["low"]),
            float(zone_raw["high"]),
            str(zone_raw["kind"]),
            int(zone_raw["touches"]),
        )
        signal = EngineSignal(
            action,
            str(payload["reason"]),
            str(payload["timeframe"]),
            zone=zone,
            protection=str(payload.get("protection", "SAFE")),
            breakout_state=str(payload.get("breakout_state", "NO_BREAKOUT")),
            entry_reference=payload.get("entry_reference"),
            stop_reference=payload.get("stop_reference"),
            test_index=payload.get("test_index"),
            confirmation_index=payload.get("confirmation_index"),
            structure_bias=str(payload.get("structure_bias", "UNKNOWN")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PaperCheckpointError("pending signal fields are invalid") from exc
    if signal.timeframe != timeframe:
        raise PaperCheckpointError("pending signal timeframe mismatch")
    return PendingSignalState(symbol, timeframe, bar_time, signal)


def save_checkpoint(checkpoint: PaperRuntimeCheckpoint, path: str | os.PathLike[str]) -> None:
    """Atomically save a versioned runtime checkpoint."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": checkpoint.version,
        "last_bar_time": _timestamp(checkpoint.last_bar_time),
        "pending_signal": _signal_to_dict(checkpoint.pending_signal) if checkpoint.pending_signal else None,
        "position_open": checkpoint.position_open,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    temp_name: str | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    except OSError as exc:
        if temp_name is not None:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass
        raise PaperCheckpointError(f"failed to save checkpoint: {exc}") from exc


def load_checkpoint(path: str | os.PathLike[str]) -> PaperRuntimeCheckpoint:
    """Load and validate a checkpoint; active positions fail closed."""
    target = Path(path)
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PaperCheckpointError(f"failed to load checkpoint: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise PaperCheckpointError("unsupported or malformed checkpoint")
    position_open = raw.get("position_open")
    if not isinstance(position_open, bool):
        raise PaperCheckpointError("position_open must be boolean")
    if position_open:
        raise PaperCheckpointError("checkpoint contains an open paper position; restore is fail-closed")
    pending = raw.get("pending_signal")
    return PaperRuntimeCheckpoint(
        last_bar_time=_parse_timestamp(raw.get("last_bar_time"), "last_bar_time"),
        pending_signal=None if pending is None else _signal_from_dict(pending),
        position_open=False,
    )


__all__ = [
    "PaperCheckpointError",
    "PendingSignalState",
    "PaperRuntimeCheckpoint",
    "save_checkpoint",
    "load_checkpoint",
]
