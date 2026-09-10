"""Fail-closed validation for completed candle streams."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


@dataclass(frozen=True)
class DataQualityReport:
    ok: bool
    reason: str
    bar_count: int
    gap_seconds: float = 0.0


def validate_closed_bars(
    bars: Iterable[object],
    *,
    timeframe_seconds: int,
    minimum_bars: int = 1,
) -> DataQualityReport:
    """Validate OHLC finiteness, timestamp ordering, and continuity.

    A gap larger than one expected bar interval is rejected. Missing candles can
    otherwise make a strategy interpret stale market structure as current data.
    """
    if timeframe_seconds <= 0 or minimum_bars <= 0:
        raise ValueError("timeframe_seconds and minimum_bars must be positive")
    items = list(bars)
    if len(items) < minimum_bars:
        return DataQualityReport(False, f"insufficient closed bars: {len(items)} < {minimum_bars}", len(items))

    previous: datetime | None = None
    for index, bar in enumerate(items):
        timestamp = getattr(bar, "time", None)
        if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
            return DataQualityReport(False, f"bar {index} timestamp must be timezone-aware", len(items))
        values = [getattr(bar, field, float("nan")) for field in ("open", "high", "low", "close")]
        if not all(math.isfinite(float(value)) for value in values):
            return DataQualityReport(False, f"bar {index} contains non-finite OHLC", len(items))
        open_, high, low, close = map(float, values)
        if high < max(open_, close) or low > min(open_, close) or low > high:
            return DataQualityReport(False, f"bar {index} has inconsistent OHLC bounds", len(items))
        current = timestamp
        if previous is not None:
            delta = (current - previous).total_seconds()
            if delta <= 0:
                return DataQualityReport(False, f"bar timestamps are not strictly increasing at index {index}", len(items))
            if delta > timeframe_seconds:
                return DataQualityReport(False, f"closed-bar gap detected: {delta:.3f}s > {timeframe_seconds}s", len(items), delta)
        previous = current

    return DataQualityReport(True, "closed-bar stream is continuous and finite", len(items))
