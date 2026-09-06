"""Realtime, closed-candle monitoring for Ariatrading research.

This module deliberately evaluates only completed candles. A live feed may
contain an in-progress candle, but that candle is never treated as confirmed
signal evidence. This prevents intrabar repainting and keeps live monitoring
consistent with historical backtests.

No order execution is implemented here.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol, Sequence

from .candles import Candle
from .engine import EngineSignal, WAIT, evaluate_long, evaluate_short
from .levels_v2 import PriceZone, find_resistance_zones, find_support_zones


@dataclass(frozen=True)
class LiveBar:
    time: datetime
    open: float
    high: float
    low: float
    close: float

    def __post_init__(self) -> None:
        if self.time.tzinfo is None:
            raise ValueError("LiveBar.time must be timezone-aware")
        if self.high < max(self.open, self.close):
            raise ValueError("high must be >= open and close")
        if self.low > min(self.open, self.close):
            raise ValueError("low must be <= open and close")
        if self.high < self.low:
            raise ValueError("high must be >= low")

    def as_dict(self) -> dict:
        return {
            "time": self.time,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
        }


class BarFeed(Protocol):
    def closed_bars(self, symbol: str, timeframe: str, count: int) -> Sequence[LiveBar]:
        """Return bars that are already closed, oldest first."""


@dataclass(frozen=True)
class LiveEvaluation:
    symbol: str
    timeframe: str
    evaluated_at: datetime
    bar_time: datetime
    signal: EngineSignal
    support: PriceZone | None
    resistance: PriceZone | None


class RealtimeMonitor:
    """Poll a BarFeed and evaluate only when a new closed candle appears."""

    def __init__(self, feed: BarFeed, symbol: str, timeframe: str, lookback: int = 100):
        if lookback < 10:
            raise ValueError("lookback must be at least 10")
        self.feed = feed
        self.symbol = symbol
        self.timeframe = timeframe
        self.lookback = lookback
        self._last_bar_time: datetime | None = None

    def evaluate_once(self) -> LiveEvaluation:
        bars = list(self.feed.closed_bars(self.symbol, self.timeframe, self.lookback))
        if len(bars) < 5:
            raise ValueError("not enough closed bars for evaluation")
        if any(bars[i].time >= bars[i + 1].time for i in range(len(bars) - 1)):
            raise ValueError("bars must be sorted oldest first")

        latest = bars[-1]
        candles = [
            Candle(b.open, b.high, b.low, b.close).as_dict() if hasattr(Candle, "as_dict")
            else {"open": b.open, "high": b.high, "low": b.low, "close": b.close}
            for b in bars
        ]

        history = candles[:-1]
        supports = find_support_zones(history)
        resistances = find_resistance_zones(history)

        long_signal = self._best_signal(
            [evaluate_long(candles, zone, self.timeframe) for zone in supports]
        )
        short_signal = self._best_signal(
            [evaluate_short(candles, zone, self.timeframe) for zone in resistances]
        )
        signal = self._select_signal(long_signal, short_signal)

        self._last_bar_time = latest.time
        return LiveEvaluation(
            symbol=self.symbol,
            timeframe=self.timeframe,
            evaluated_at=datetime.now(timezone.utc),
            bar_time=latest.time,
            signal=signal,
            support=supports[-1] if supports else None,
            resistance=resistances[-1] if resistances else None,
        )

    @staticmethod
    def _best_signal(signals: Sequence[EngineSignal]) -> EngineSignal:
        if not signals:
            raise ValueError("no candidate zones")
        actionable = [s for s in signals if s.action != WAIT]
        if not actionable:
            return signals[-1]
        return max(
            actionable,
            key=lambda s: (s.score.total if s.score is not None else -1, s.entry_reference or 0.0),
        )

    @staticmethod
    def _select_signal(long_signal: EngineSignal, short_signal: EngineSignal) -> EngineSignal:
        long_ok = long_signal.action == "LONG"
        short_ok = short_signal.action == "SHORT"
        if long_ok and not short_ok:
            return long_signal
        if short_ok and not long_ok:
            return short_signal
        if long_ok and short_ok:
            long_score = long_signal.score.total if long_signal.score else -1
            short_score = short_signal.score.total if short_signal.score else -1
            if long_score != short_score:
                return long_signal if long_score > short_score else short_signal
        return EngineSignal(WAIT, "no unambiguous realtime setup", long_signal.timeframe)
