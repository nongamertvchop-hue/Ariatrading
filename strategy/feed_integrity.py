"""Strict structural validation for timestamped OHLC feed batches.

This layer is independent from strategy decisions. It rejects observations that
cannot be interpreted safely: malformed OHLC geometry, mixed timestamp
normalization, duplicate/out-of-order bars, and timestamps that are not aligned
to the configured timeframe grid.

Missing-bar detection is opt-in because FX feeds can legitimately have
session/weekend gaps. Callers that require a contiguous research/live stream
can enable ``require_contiguous`` at the feed boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Protocol, Sequence

from .timeframe import bar_duration, get_timeframe_config


class _BarLike(Protocol):
    time: datetime
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class FeedIntegrityReport:
    """Structural feed validation result."""

    ok: bool
    reason: str
    checked_bars: int
    duplicate_count: int = 0
    out_of_order_count: int = 0
    misaligned_count: int = 0
    missing_count: int = 0


def validate_feed_batch(
    bars: Sequence[_BarLike],
    timeframe: str,
    *,
    require_utc: bool = True,
    require_contiguous: bool = False,
) -> FeedIntegrityReport:
    """Validate a timestamped OHLC batch without making trading decisions."""
    get_timeframe_config(timeframe)
    if not bars:
        return FeedIntegrityReport(False, "empty feed", 0)

    duration_seconds = int(bar_duration(timeframe).total_seconds())
    if duration_seconds <= 0:
        raise ValueError("timeframe duration must be positive")

    duplicate_count = 0
    out_of_order_count = 0
    misaligned_count = 0
    missing_count = 0
    previous_time: datetime | None = None

    for bar in bars:
        values = (bar.open, bar.high, bar.low, bar.close)
        if not all(isfinite(float(value)) for value in values):
            return FeedIntegrityReport(False, "non-finite OHLC value", len(bars))
        if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close) or bar.high < bar.low:
            return FeedIntegrityReport(False, "invalid OHLC geometry", len(bars))
        if bar.time.tzinfo is None or bar.time.utcoffset() is None:
            return FeedIntegrityReport(False, "bar timestamp must be timezone-aware", len(bars))
        if require_utc and bar.time.utcoffset() != timezone.utc.utcoffset(bar.time):
            return FeedIntegrityReport(False, "bar timestamp must use UTC", len(bars))

        normalized = bar.time.astimezone(timezone.utc)
        epoch_seconds = int(normalized.timestamp())
        if epoch_seconds % duration_seconds != 0:
            misaligned_count += 1
        if previous_time is not None:
            delta = int((normalized - previous_time).total_seconds())
            if delta == 0:
                duplicate_count += 1
            elif delta < 0:
                out_of_order_count += 1
            elif require_contiguous and delta != duration_seconds:
                missing_count += max(0, delta // duration_seconds - 1)
        previous_time = normalized

    if duplicate_count:
        return FeedIntegrityReport(False, "duplicate bar timestamps", len(bars), duplicate_count, out_of_order_count, misaligned_count, missing_count)
    if out_of_order_count:
        return FeedIntegrityReport(False, "bars must be strictly chronological", len(bars), duplicate_count, out_of_order_count, misaligned_count, missing_count)
    if misaligned_count:
        return FeedIntegrityReport(False, "bar timestamp is not aligned to timeframe grid", len(bars), duplicate_count, out_of_order_count, misaligned_count, missing_count)
    if missing_count:
        return FeedIntegrityReport(False, "missing candle interval detected", len(bars), duplicate_count, out_of_order_count, misaligned_count, missing_count)

    return FeedIntegrityReport(True, "feed integrity passed", len(bars))


__all__ = ["FeedIntegrityReport", "validate_feed_batch"]
