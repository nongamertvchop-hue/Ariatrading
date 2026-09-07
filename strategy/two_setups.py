"""Automatic orchestration for Ariatrading's two core price-action setups.

The only trade directions exposed here are LONG from support and SHORT from
resistance. Zones are built exclusively from candles that existed before the
current signal candle, then the existing sequence engine decides whether the
latest completed candle confirms the setup.

No indicators, forecasts, or orders are introduced by this module.
"""

from dataclasses import dataclass

from .engine import EngineSignal, LONG, SHORT, WAIT, evaluate_long, evaluate_short
from .levels_v2 import PriceZone, find_resistance_zones, find_support_zones
from .timeframe import adaptive_zone_tolerance, get_timeframe_config


@dataclass(frozen=True)
class TwoSetupResult:
    """Result of evaluating both core setups at the latest completed candle."""

    signal: EngineSignal
    support_zones: tuple[PriceZone, ...]
    resistance_zones: tuple[PriceZone, ...]


def _zone_distance(zone: PriceZone, price: float) -> float:
    """Distance from a price to a zone; zero when the price is inside it."""
    if zone.low <= price <= zone.high:
        return 0.0
    return min(abs(price - zone.low), abs(price - zone.high))


def _rank_zones(zones: list[PriceZone], price: float) -> list[PriceZone]:
    """Prefer nearby zones, then zones with more independent reactions."""
    return sorted(zones, key=lambda zone: (_zone_distance(zone, price), -zone.touches, zone.center))


def evaluate_two_setups(
    candles: list[dict],
    timeframe: str,
    *,
    strength: int = 2,
    min_touches: int = 2,
    max_test_age: int = 3,
) -> TwoSetupResult:
    """Evaluate LONG-from-support and SHORT-from-resistance.

    The final candle is the signal/confirmation candle and is never used to
    construct support/resistance zones. This preserves causal ordering for
    live evaluation and makes the function suitable for walk-forward replay.
    """
    get_timeframe_config(timeframe)
    if strength < 1:
        raise ValueError("strength must be >= 1")
    if min_touches < 1:
        raise ValueError("min_touches must be >= 1")
    if max_test_age < 1:
        raise ValueError("max_test_age must be >= 1")
    if len(candles) < max(8, strength * 2 + 3):
        signal = EngineSignal(
            action=WAIT,
            reason="not enough completed candles to build confirmed zones",
            timeframe=timeframe,
        )
        return TwoSetupResult(signal, (), ())

    history = candles[:-1]
    tolerance = adaptive_zone_tolerance(history, timeframe)
    supports = find_support_zones(
        history,
        strength=strength,
        tolerance=tolerance,
        min_touches=min_touches,
    )
    resistances = find_resistance_zones(
        history,
        strength=strength,
        tolerance=tolerance,
        min_touches=min_touches,
    )

    current_close = float(candles[-1]["close"])
    ranked_supports = _rank_zones(supports, current_close)
    ranked_resistances = _rank_zones(resistances, current_close)

    candidates: list[tuple[float, int, EngineSignal]] = []
    for zone in ranked_supports:
        result = evaluate_long(candles, zone, timeframe, max_test_age=max_test_age)
        if result.action == LONG:
            candidates.append((_zone_distance(zone, current_close), 0, result))
            break
    for zone in ranked_resistances:
        result = evaluate_short(candles, zone, timeframe, max_test_age=max_test_age)
        if result.action == SHORT:
            candidates.append((_zone_distance(zone, current_close), 1, result))
            break

    if candidates:
        _, _, signal = min(candidates, key=lambda item: (item[0], item[1]))
        return TwoSetupResult(signal, tuple(supports), tuple(resistances))

    return TwoSetupResult(
        EngineSignal(
            action=WAIT,
            reason="no confirmed support/rejection or resistance/rejection setup",
            timeframe=timeframe,
        ),
        tuple(supports),
        tuple(resistances),
    )
