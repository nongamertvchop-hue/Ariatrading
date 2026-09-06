"""Deterministic probabilistic forecasting for closed-candle research.

The forecast estimates likely *scenarios*, not certainty. It uses only candles
available at the evaluation timestamp and never reads future bars.

This module is intentionally independent from entry logic: LONG/SHORT/WAIT
remain the only trading setup actions in the core engine.
"""

from dataclasses import dataclass
from math import exp, isfinite
from statistics import mean
from typing import Sequence

from .candles import Candle, candle_pressure
from .levels_v2 import PriceZone

UP = "UP"
DOWN = "DOWN"
FLAT = "FLAT"


@dataclass(frozen=True)
class HorizonForecast:
    horizon: int
    up_probability: float
    flat_probability: float
    down_probability: float
    expected_return: float
    expected_close: float

    @property
    def direction(self) -> str:
        probabilities = {
            UP: self.up_probability,
            FLAT: self.flat_probability,
            DOWN: self.down_probability,
        }
        return max(probabilities, key=probabilities.get)


@dataclass(frozen=True)
class ScenarioForecast:
    name: str
    probability: float
    path: tuple[str, ...]


@dataclass(frozen=True)
class ForecastResult:
    as_of: object
    current_close: float
    horizons: tuple[HorizonForecast, ...]
    scenarios: tuple[ScenarioForecast, ...]
    confidence: float
    model: str = "deterministic-empirical-v1"


def _validate_candles(candles: Sequence[dict]) -> None:
    if not candles:
        raise ValueError("candles must not be empty")
    for candle in candles:
        for key in ("open", "high", "low", "close"):
            if key not in candle or not isfinite(float(candle[key])):
                raise ValueError(f"invalid candle field: {key}")


def _returns(candles: Sequence[dict]) -> list[float]:
    return [
        float(candles[i]["close"]) / float(candles[i - 1]["close"]) - 1.0
        for i in range(1, len(candles))
        if float(candles[i - 1]["close"]) != 0
    ]


def _empirical_direction(returns: Sequence[float], horizon: int) -> tuple[float, float, float, float]:
    """Estimate direction from historical rolling horizon returns.

    Observations are formed only from completed bars. The latest observation is
    deliberately excluded from the training sample because it is the forecast
    origin, preventing accidental use of its future horizon.
    """
    if len(returns) < horizon + 4:
        return 1 / 3, 1 / 3, 1 / 3, 0.0

    samples: list[float] = []
    closes = []
    # returns[k:k+horizon] represents movement after close[k]. The final
    # available origin is the latest close, so it cannot be a training sample.
    for origin in range(0, len(returns) - horizon):
        samples.append(sum(returns[origin:origin + horizon]))
        closes.append(origin)

    if not samples:
        return 1 / 3, 1 / 3, 1 / 3, 0.0

    scale = max(mean(abs(x) for x in samples), 1e-9)
    threshold = scale * 0.35
    up = sum(x > threshold for x in samples)
    down = sum(x < -threshold for x in samples)
    flat = len(samples) - up - down
    total = float(len(samples))
    expected = mean(samples)
    return up / total, flat / total, down / total, expected


def _trend_bias(returns: Sequence[float]) -> float:
    recent = list(returns[-8:])
    if not recent:
        return 0.0
    weights = range(1, len(recent) + 1)
    numerator = sum(r * w for r, w in zip(recent, weights))
    denominator = sum(weights)
    return max(-1.0, min(1.0, numerator / max(denominator, 1)))


def _zone_bias(close: float, support: PriceZone | None, resistance: PriceZone | None) -> float:
    """Positive near support, negative near resistance, neutral in between."""
    values: list[float] = []
    if support is not None and support.high >= close:
        distance = max(close - support.high, 0.0)
        width = max(support.high - support.low, close * 0.001, 1e-9)
        values.append(max(-1.0, 1.0 - distance / width))
    elif support is not None:
        distance = (close - support.high) / max(abs(close), 1e-9)
        values.append(max(-0.25, 0.5 - distance * 50.0))
    if resistance is not None and resistance.low <= close:
        distance = max(resistance.low - close, 0.0)
        width = max(resistance.high - resistance.low, close * 0.001, 1e-9)
        values.append(min(1.0, -1.0 + distance / width))
    elif resistance is not None:
        distance = (resistance.low - close) / max(abs(close), 1e-9)
        values.append(min(0.25, -0.5 + distance * 50.0))
    return mean(values) if values else 0.0


def _normalise(up: float, flat: float, down: float) -> tuple[float, float, float]:
    values = [max(0.0, up), max(0.0, flat), max(0.0, down)]
    total = sum(values)
    return tuple(v / total for v in values)  # type: ignore[return-value]


def forecast(
    candles: Sequence[dict],
    horizons: Sequence[int] = (1, 3, 5),
    support: PriceZone | None = None,
    resistance: PriceZone | None = None,
) -> ForecastResult:
    """Forecast direction and likely candle path from closed candles only."""
    _validate_candles(candles)
    if any(h < 1 for h in horizons):
        raise ValueError("horizons must be positive")
    if any(horizons[i] >= horizons[i + 1] for i in range(len(horizons) - 1)):
        raise ValueError("horizons must be strictly increasing")

    latest = candles[-1]
    close = float(latest["close"])
    returns = _returns(candles)
    trend = _trend_bias(returns)
    pressure = candle_pressure(Candle(float(latest["open"]), float(latest["high"]), float(latest["low"]), close))
    pressure_bias = {"BUYING": 0.18, "SELLING": -0.18, "NEUTRAL": 0.0}[pressure]
    zone_bias = _zone_bias(close, support, resistance)

    results: list[HorizonForecast] = []
    for horizon in horizons:
        up, flat, down, empirical = _empirical_direction(returns, horizon)
        directional_bias = max(-0.35, min(0.35, trend * 0.45 + pressure_bias + zone_bias * 0.20))
        up, flat, down = _normalise(up + directional_bias, flat, down - directional_bias)
        expected = empirical + directional_bias * max(mean(abs(r) for r in returns[-20:]) if returns else 0.0, 0.0) * horizon
        results.append(HorizonForecast(horizon, up, flat, down, expected, close * (1.0 + expected)))

    first = results[0]
    directional_strength = abs(first.up_probability - first.down_probability)
    sample_factor = min(1.0, len(returns) / 100.0)
    confidence = max(0.0, min(1.0, 0.45 * directional_strength + 0.55 * sample_factor))

    up_p = first.up_probability
    down_p = first.down_probability
    flat_p = first.flat_probability
    scenarios = [
        ScenarioForecast("bullish-continuation", up_p, ("TEST_SUPPORT", "REJECT/RECLAIM", "BULLISH_CONFIRM")),
        ScenarioForecast("bearish-continuation", down_p, ("TEST_RESISTANCE", "REJECT/RECLAIM", "BEARISH_CONFIRM")),
        ScenarioForecast("range/unclear", flat_p, ("TEST", "NO_CLEAR_CONFIRMATION", "WAIT")),
    ]
    scenarios.sort(key=lambda s: s.probability, reverse=True)

    as_of = latest.get("time")
    return ForecastResult(as_of, close, tuple(results), tuple(scenarios), confidence)
