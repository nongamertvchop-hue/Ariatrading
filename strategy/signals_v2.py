"""Rule engine for the two basic price-action setups.

LONG  = support is tested, then a bullish rejection/confirmation appears.
SHORT = resistance is tested, then a bearish rejection/confirmation appears.
WAIT  = the setup is incomplete or invalidated.

Educational/demo only. No orders are placed here.
"""

from dataclasses import dataclass

from .candles import Candle, candle_pressure
from .levels_v2 import PriceZone, SUPPORT, RESISTANCE

LONG = "LONG"
SHORT = "SHORT"
WAIT = "WAIT"


@dataclass(frozen=True)
class Signal:
    action: str
    reason: str
    zone: PriceZone | None = None


def candle_touches_zone(candle: Candle, zone: PriceZone) -> bool:
    """True when the candle trades into the zone."""
    return candle.low <= zone.high and candle.high >= zone.low


def support_holds(candle: Candle, zone: PriceZone) -> bool:
    """Support test: price enters the zone but closes back above it."""
    return candle_touches_zone(candle, zone) and candle.close > zone.high


def resistance_holds(candle: Candle, zone: PriceZone) -> bool:
    """Resistance test: price enters the zone but closes back below it."""
    return candle_touches_zone(candle, zone) and candle.close < zone.low


def evaluate_long(candle: Candle, support: PriceZone) -> Signal:
    if support.kind != SUPPORT:
        raise ValueError("zone must be SUPPORT")
    if not candle_touches_zone(candle, support):
        return Signal(WAIT, "price has not tested support", support)
    if candle.close < support.low:
        return Signal(WAIT, "support is broken", support)
    if support_holds(candle, support) and candle_pressure(candle) == "BUYING":
        return Signal(LONG, "support tested and buyers confirmed", support)
    return Signal(WAIT, "support tested but confirmation is insufficient", support)


def evaluate_short(candle: Candle, resistance: PriceZone) -> Signal:
    if resistance.kind != RESISTANCE:
        raise ValueError("zone must be RESISTANCE")
    if not candle_touches_zone(candle, resistance):
        return Signal(WAIT, "price has not tested resistance", resistance)
    if candle.close > resistance.high:
        return Signal(WAIT, "resistance is broken", resistance)
    if resistance_holds(candle, resistance) and candle_pressure(candle) == "SELLING":
        return Signal(SHORT, "resistance tested and sellers confirmed", resistance)
    return Signal(WAIT, "resistance tested but confirmation is insufficient", resistance)
