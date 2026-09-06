"""Decision engine for the two price-action setups.

Signals are educational/demo only. This module does not place orders.
"""

from .candles import Candle, candle_pressure
from .levels import PriceLevel


LONG = "LONG"
SHORT = "SHORT"
WAIT = "WAIT"


def in_zone(price: float, level: PriceLevel, tolerance: float) -> bool:
    return abs(price - level.price) <= tolerance


def check_long_setup(candle: Candle, support: PriceLevel, zone_tolerance: float) -> str:
    """Return LONG only when price tests support and buyers confirm."""
    if support.kind != "SUPPORT":
        raise ValueError("level must be SUPPORT")
    if not in_zone(candle.low, support, zone_tolerance):
        return WAIT
    return LONG if candle_pressure(candle) == "BUYING" else WAIT


def check_short_setup(candle: Candle, resistance: PriceLevel, zone_tolerance: float) -> str:
    """Return SHORT only when price tests resistance and sellers confirm."""
    if resistance.kind != "RESISTANCE":
        raise ValueError("level must be RESISTANCE")
    if not in_zone(candle.high, resistance, zone_tolerance):
        return WAIT
    return SHORT if candle_pressure(candle) == "SELLING" else WAIT
