"""Strict historical OHLCV loading for reproducible paper research.

The loader accepts CSV data from an explicitly selected source, validates the
schema and candle geometry, normalizes UTC timestamps, and never fabricates
missing market observations.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path

REQUIRED_COLUMNS = ("datetime", "open", "high", "low", "close", "volume")


def load_ohlcv_csv(path: str | Path, *, max_rows: int | None = None) -> list[dict]:
    source = Path(path)
    try:
        with source.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or not set(REQUIRED_COLUMNS).issubset(reader.fieldnames):
                raise ValueError("historical CSV is missing required OHLCV columns")
            rows: list[dict] = []
            previous: datetime | None = None
            for raw in reader:
                timestamp = _parse_timestamp(raw.get("datetime"))
                values = {key: float(raw[key]) for key in ("open", "high", "low", "close", "volume")}
                if not all(isfinite(values[key]) for key in values):
                    raise ValueError("historical CSV contains non-finite values")
                if min(values["open"], values["high"], values["low"], values["close"]) <= 0:
                    raise ValueError("historical prices must be > 0")
                if values["high"] < max(values["open"], values["close"]):
                    raise ValueError("historical candle high is below open/close")
                if values["low"] > min(values["open"], values["close"]):
                    raise ValueError("historical candle low is above open/close")
                if values["high"] < values["low"] or values["volume"] < 0:
                    raise ValueError("historical candle geometry/volume is invalid")
                if previous is not None and timestamp <= previous:
                    raise ValueError("historical timestamps must be strictly chronological")
                previous = timestamp
                rows.append({"time": timestamp, **values})
                if max_rows is not None and len(rows) >= max_rows:
                    break
    except OSError as exc:
        raise ValueError(f"unable to read historical CSV: {exc}") from exc
    return rows


def _parse_timestamp(value: str | None) -> datetime:
    if not value:
        raise ValueError("historical candle is missing datetime")
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"invalid historical timestamp: {value}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("historical timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


__all__ = ["REQUIRED_COLUMNS", "load_ohlcv_csv"]
