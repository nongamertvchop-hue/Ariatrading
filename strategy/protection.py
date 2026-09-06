"""False-break protection for the two basic price-action setups.

The goal is not to predict the market. The filter simply refuses a setup when
price has moved too far through a support/resistance zone. This creates a
"no-entry danger zone" around the level and keeps the signal engine from
chasing obvious breaks.

Educational/demo only. No orders are placed here.
"""

from .candles import Candle
from .levels_v2 import PriceZone, SUPPORT, RESISTANCE


class Protection:
    """Result of the false-break protection check."""

    SAFE = "SAFE"
    DANGER = "DANGER"
    BROKEN = "BROKEN"


def support_state(candle: Candle, support: PriceZone, danger_buffer: float) -> str:
    """Classify a support test as safe, dangerous, or broken.

    SAFE: price tested the zone but did not close below it and did not make
    an excessive penetration beneath the zone.
    DANGER: the wick penetrated beyond the zone but only inside the buffer;
    wait for a cleaner confirmation instead of entering immediately.
    BROKEN: the candle closes below the zone/buffer, so the long premise is
    invalidated.
    """
    if support.kind != SUPPORT:
        raise ValueError("zone must be SUPPORT")
    if danger_buffer < 0:
        raise ValueError("danger_buffer must be >= 0")

    if candle.close < support.low - danger_buffer:
        return Protection.BROKEN
    if candle.low < support.low:
        return Protection.DANGER
    return Protection.SAFE


def resistance_state(candle: Candle, resistance: PriceZone, danger_buffer: float) -> str:
    """Classify a resistance test as safe, dangerous, or broken."""
    if resistance.kind != RESISTANCE:
        raise ValueError("zone must be RESISTANCE")
    if danger_buffer < 0:
        raise ValueError("danger_buffer must be >= 0")

    if candle.close > resistance.high + danger_buffer:
        return Protection.BROKEN
    if candle.high > resistance.high:
        return Protection.DANGER
    return Protection.SAFE


def long_entry_allowed(candle: Candle, support: PriceZone, danger_buffer: float) -> bool:
    """Allow LONG only when support has not entered the danger/broken state."""
    return support_state(candle, support, danger_buffer) == Protection.SAFE


def short_entry_allowed(candle: Candle, resistance: PriceZone, danger_buffer: float) -> bool:
    """Allow SHORT only when resistance has not entered the danger/broken state."""
    return resistance_state(candle, resistance, danger_buffer) == Protection.SAFE
