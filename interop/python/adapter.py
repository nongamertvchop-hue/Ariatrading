"""Canonical market-data validator used by the polyglot data plane."""

from __future__ import annotations

import math
import json
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class Candle:
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


def validate_candle(record: dict[str, Any]) -> Candle:
    required = ("time", "open", "high", "low", "close")
    missing = [key for key in required if key not in record]
    if missing:
        raise ValueError(f"missing fields: {','.join(missing)}")
    time = int(record["time"])
    values = {key: float(record[key]) for key in required[1:]}
    if time <= 0 or not all(math.isfinite(v) and v > 0 for v in values.values()):
        raise ValueError("time/prices must be finite and positive")
    if values["high"] < max(values["open"], values["close"]):
        raise ValueError("high is below open/close")
    if values["low"] > min(values["open"], values["close"]):
        raise ValueError("low is above open/close")
    volume = record.get("volume")
    if volume is not None and (not math.isfinite(float(volume)) or float(volume) < 0):
        raise ValueError("volume must be finite and non-negative")
    return Candle(time=time, volume=None if volume is None else float(volume), **values)


def validate_sequence(records: Iterable[dict[str, Any]]) -> list[Candle]:
    candles: list[Candle] = []
    previous = 0
    for record in records:
        candle = validate_candle(record)
        if candle.time <= previous:
            raise ValueError("timestamps must be strictly increasing")
        candles.append(candle)
        previous = candle.time
    return candles


def to_jsonl(candles: Iterable[Candle]) -> str:
    rows = []
    for candle in candles:
        row = {
            "ok": True,
            "time": candle.time,
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
        }
        if candle.volume is not None:
            row["volume"] = candle.volume
        rows.append(json.dumps(row, separators=(",", ":")))
    return "\n".join(rows) + ("\n" if rows else "")


__all__ = ["Candle", "validate_candle", "validate_sequence", "to_jsonl"]
