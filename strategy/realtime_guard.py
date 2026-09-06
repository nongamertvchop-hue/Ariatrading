"""Realtime data-quality and state guards for research monitoring.

The guard layer sits before forecasting/strategy evaluation. It rejects stale,
non-monotonic, malformed, duplicate, or incomplete observations so bad feed
data cannot silently become a signal. Research/paper monitoring only.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Sequence, Protocol

from .timeframe import bar_duration, get_timeframe_config


class _BarLike(Protocol):
    time: datetime
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class DataQuality:
    ok: bool
    reason: str
    latest_time: datetime | None = None
    age_seconds: float | None = None


class RealtimeGuard:
    """Validate closed bars and suppress duplicate/stale evaluations."""

    def __init__(self, timeframe: str, max_staleness_bars: int = 2):
        get_timeframe_config(timeframe)
        if max_staleness_bars < 1:
            raise ValueError("max_staleness_bars must be >= 1")
        self.timeframe = timeframe
        self.max_staleness_bars = max_staleness_bars
        self._last_evaluated: datetime | None = None

    @property
    def last_evaluated(self) -> datetime | None:
        return self._last_evaluated

    def validate(self, bars: Sequence[_BarLike], now: datetime | None = None) -> DataQuality:
        if not bars:
            return DataQuality(False, "empty feed")
        for bar in bars:
            if bar.time.tzinfo is None:
                return DataQuality(False, "bar timestamp must be timezone-aware", bar.time)
            values = (bar.open, bar.high, bar.low, bar.close)
            if not all(isfinite(float(v)) for v in values):
                return DataQuality(False, "non-finite OHLC value", bar.time)
            if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close) or bar.high < bar.low:
                return DataQuality(False, "invalid OHLC geometry", bar.time)
        for left, right in zip(bars, bars[1:]):
            if left.time >= right.time:
                return DataQuality(False, "bars must be strictly chronological", right.time)
        latest = bars[-1]
        reference = now or datetime.now(timezone.utc)
        if reference.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        age = (reference - latest.time).total_seconds()
        max_age = bar_duration(self.timeframe).total_seconds() * self.max_staleness_bars
        if age < 0:
            return DataQuality(False, "latest bar timestamp is in the future", latest.time, age)
        if age > max_age:
            return DataQuality(False, "feed is stale", latest.time, age)
        if self._last_evaluated is not None and latest.time <= self._last_evaluated:
            return DataQuality(False, "duplicate or old closed bar", latest.time, age)
        return DataQuality(True, "ok", latest.time, age)

    def accept(self, bars: Sequence[_BarLike], now: datetime | None = None) -> DataQuality:
        quality = self.validate(bars, now)
        if quality.ok:
            self._last_evaluated = bars[-1].time
        return quality


def expected_closed_bar_open(now: datetime, timeframe: str) -> datetime:
    """Return the start time of the currently forming bar."""
    get_timeframe_config(timeframe)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    duration = bar_duration(timeframe)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    elapsed = (now.astimezone(timezone.utc) - epoch).total_seconds()
    bucket = int(elapsed // duration.total_seconds())
    return epoch + timedelta(seconds=bucket * duration.total_seconds())
