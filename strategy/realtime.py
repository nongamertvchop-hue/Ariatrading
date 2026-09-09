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
from .feed_integrity import validate_feed_batch
from .forecast import ForecastResult, forecast
from .levels_v2 import PriceZone, find_resistance_zones, find_support_zones
from .market_snapshot import MarketSnapshot
from .realtime_guard import RealtimeGuard
from .realtime_supervisor import ALLOW, SupervisorDecision, supervise
from .signal_event import build_signal_event_id
from .timeframe import adaptive_zone_tolerance, get_timeframe_config


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
    forecast: ForecastResult | None = None
    data_quality: str = "ok"
    supervisor: SupervisorDecision | None = None
    snapshot: MarketSnapshot | None = None

    @property
    def event_id(self) -> str:
        """Stable research identity for this closed-candle decision."""
        score = None if self.signal.score is None else {"total": self.signal.score.total}
        zone = None if self.signal.zone is None else {
            "kind": self.signal.zone.kind,
            "low": self.signal.zone.low,
            "high": self.signal.zone.high,
            "touches": self.signal.zone.touches,
        }
        return build_signal_event_id({
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "bar_time": self.bar_time.isoformat(),
            "signal": self.signal.action,
            "state": self.signal.state,
            "breakout_state": self.signal.breakout_state,
            "price": self.snapshot.current_close if self.snapshot is not None else None,
            "entry_reference": self.signal.entry_reference,
            "stop_reference": self.signal.stop_reference if self.signal.action != WAIT else None,
            "structure_bias": self.signal.structure_bias,
            "score": score,
            "zone": zone,
        })


class RealtimeMonitor:
    """Poll a BarFeed with quality and consistency checks."""

    def __init__(self, feed: BarFeed, symbol: str, timeframe: str, lookback: int = 100,
                 max_staleness_bars: int = 2, min_forecast_confidence: float = 0.45):
        get_timeframe_config(timeframe)
        if lookback < 10:
            raise ValueError("lookback must be at least 10")
        self.feed = feed
        self.symbol = symbol
        self.timeframe = timeframe
        self.lookback = lookback
        self.guard = RealtimeGuard(timeframe, max_staleness_bars=max_staleness_bars)
        self.min_forecast_confidence = min_forecast_confidence
        self._last_bar_time: datetime | None = None

    @property
    def last_bar_time(self) -> datetime | None:
        """Timestamp of the most recently evaluated closed candle."""
        return self._last_bar_time

    def evaluate_once(self, now: datetime | None = None) -> LiveEvaluation | None:
        """Evaluate a newly closed candle, or return None if data is not new/valid."""
        bars = list(self.feed.closed_bars(self.symbol, self.timeframe, self.lookback))
        if len(bars) < 5:
            raise ValueError("not enough closed bars for evaluation")

        integrity = validate_feed_batch(bars, self.timeframe)
        if not integrity.ok:
            raise RuntimeError(f"realtime feed integrity rejected: {integrity.reason}")

        quality = self.guard.validate(bars, now=now)
        if not quality.ok:
            if quality.reason == "duplicate or old closed bar":
                return None
            raise RuntimeError(f"realtime data rejected: {quality.reason}")

        latest = bars[-1]
        candles = [b.as_dict() for b in bars]
        history = candles[:-1]
        tolerance = adaptive_zone_tolerance(history, self.timeframe)
        supports = find_support_zones(history, tolerance=tolerance)
        resistances = find_resistance_zones(history, tolerance=tolerance)

        long_signal = self._best_signal(
            [evaluate_long(candles, zone, self.timeframe) for zone in supports]
        ) if supports else EngineSignal(WAIT, "no support zone", self.timeframe)
        short_signal = self._best_signal(
            [evaluate_short(candles, zone, self.timeframe) for zone in resistances]
        ) if resistances else EngineSignal(WAIT, "no resistance zone", self.timeframe)
        signal = self._select_signal(long_signal, short_signal)

        support = self._nearest_support(latest.close, supports)
        resistance = self._nearest_resistance(latest.close, resistances)
        forecast_result = forecast(candles, support=support, resistance=resistance)
        supervisor = supervise(
            signal,
            forecast_result=forecast_result,
            min_confidence=self.min_forecast_confidence,
        )
        final_signal = signal
        if supervisor.action != ALLOW:
            final_signal = EngineSignal(
                WAIT,
                "realtime supervisor: " + "; ".join(supervisor.reasons),
                self.timeframe,
                zone=signal.zone,
                protection="BLOCKED",
                breakout_state=signal.breakout_state,
                entry_reference=signal.entry_reference,
                test_index=signal.test_index,
                confirmation_index=signal.confirmation_index,
                structure_bias=signal.structure_bias,
                score=signal.score,
                state=signal.state,
            )

        snapshot = MarketSnapshot(
            symbol=self.symbol,
            timeframe=self.timeframe,
            bar_time=latest.time,
            candle=Candle(latest.open, latest.high, latest.low, latest.close),
            current_close=latest.close,
            support=support,
            resistance=resistance,
            forecast=forecast_result,
            data_quality=quality,
        )

        self.guard.accept(bars, now=now)
        self._last_bar_time = latest.time
        return LiveEvaluation(
            symbol=self.symbol,
            timeframe=self.timeframe,
            evaluated_at=datetime.now(timezone.utc),
            bar_time=latest.time,
            signal=final_signal,
            support=support,
            resistance=resistance,
            forecast=forecast_result,
            data_quality=quality.reason,
            supervisor=supervisor,
            snapshot=snapshot,
        )

    @staticmethod
    def _best_signal(signals: Sequence[EngineSignal]) -> EngineSignal:
        if not signals:
            raise ValueError("no candidate zones")
        return max(
            signals,
            key=lambda s: (
                1 if s.action != WAIT else 0,
                s.score.total if s.score is not None else -1,
                s.entry_reference or 0.0,
            ),
        )

    @staticmethod
    def _nearest_support(price: float, zones: Sequence[PriceZone]) -> PriceZone | None:
        candidates = [z for z in zones if z.center <= price or z.low <= price <= z.high]
        return min(
            candidates,
            key=lambda z: (0.0 if z.low <= price <= z.high else price - z.high, -z.touches),
            default=None,
        )

    @staticmethod
    def _nearest_resistance(price: float, zones: Sequence[PriceZone]) -> PriceZone | None:
        candidates = [z for z in zones if z.center >= price or z.low <= price <= z.high]
        return min(
            candidates,
            key=lambda z: (0.0 if z.low <= price <= z.high else z.low - price, -z.touches),
            default=None,
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
