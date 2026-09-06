"""Deterministic closed-candle replay for forecast research.

Replay is deliberately paper/research only. It feeds each prefix of a
historical series into the same forecast engine, so repeated runs over the same
input produce identical forecasts and cannot use future candles.
"""

from dataclasses import dataclass
from typing import Sequence

from .forecast import ForecastResult, forecast
from .levels_v2 import find_resistance_zones, find_support_zones
from .timeframe import adaptive_zone_tolerance, get_timeframe_config


@dataclass(frozen=True)
class ReplayPoint:
    index: int
    forecast: ForecastResult


@dataclass(frozen=True)
class ReplayResult:
    timeframe: str
    points: tuple[ReplayPoint, ...]

    @property
    def count(self) -> int:
        return len(self.points)

    def directions(self, horizon: int = 1) -> tuple[str, ...]:
        return tuple(
            next(h for h in point.forecast.horizons if h.horizon == horizon).direction
            for point in self.points
        )


def replay_forecasts(
    candles: Sequence[dict],
    timeframe: str,
    warmup: int | None = None,
    horizons: Sequence[int] = (1, 3, 5),
) -> ReplayResult:
    """Replay forecasts chronologically using only data available at each bar."""
    config = get_timeframe_config(timeframe)
    if not candles:
        return ReplayResult(timeframe, ())
    if any(candles[i].get("time") >= candles[i + 1].get("time") for i in range(len(candles) - 1)
           if candles[i].get("time") is not None and candles[i + 1].get("time") is not None):
        raise ValueError("candles must be sorted oldest first")

    start = min(max(config.lookback + 2, 10, warmup or 0), len(candles))
    points: list[ReplayPoint] = []
    for i in range(start, len(candles)):
        history = list(candles[:i + 1])
        zone_history = history[:-1]
        tolerance = adaptive_zone_tolerance(zone_history, timeframe)
        supports = find_support_zones(zone_history, tolerance=tolerance)
        resistances = find_resistance_zones(zone_history, tolerance=tolerance)
        current = history[-1]
        close = float(current["close"])
        support = min(
            (z for z in supports if z.center <= close or z.low <= close <= z.high),
            key=lambda z: abs(z.center - close), default=None,
        )
        resistance = min(
            (z for z in resistances if z.center >= close or z.low <= close <= z.high),
            key=lambda z: abs(z.center - close), default=None,
        )
        points.append(ReplayPoint(i, forecast(history, horizons, support, resistance)))
    return ReplayResult(timeframe, tuple(points))
