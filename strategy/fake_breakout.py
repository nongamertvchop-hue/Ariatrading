"""Fake-breakout filter for the two basic support/resistance setups.

A breakout is treated as suspicious when price briefly trades beyond a zone
but the candle closes back inside the zone. A confirmed break requires a close
beyond the zone plus a configurable buffer. The filter is deliberately
conservative: ambiguous cases return WAIT.

Educational/demo only. No orders are placed here.
"""

from dataclasses import dataclass

from .candles import Candle
from .levels_v2 import PriceZone, SUPPORT, RESISTANCE


FAKE_BREAKOUT = "FAKE_BREAKOUT"
TRUE_BREAKOUT = "TRUE_BREAKOUT"
NO_BREAKOUT = "NO_BREAKOUT"
WAIT = "WAIT"


@dataclass(frozen=True)
class BreakoutResult:
    state: str
    reason: str


def classify_support_breakout(
    candle: Candle,
    support: PriceZone,
    confirmation_buffer: float = 0.0002,
) -> BreakoutResult:
    """Classify a move through support.

    - Fake breakout: wick goes below support, but close returns above support.
    - True breakout: close is below support by at least confirmation_buffer.
    - No breakout: price never trades below the zone.
    - WAIT: price closes below the zone, but not far enough to confirm.
    """
    if support.kind != SUPPORT:
        raise ValueError("zone must be SUPPORT")
    if confirmation_buffer < 0:
        raise ValueError("confirmation_buffer must be >= 0")

    if candle.low >= support.low:
        return BreakoutResult(NO_BREAKOUT, "price did not break below support")
    if candle.close >= support.low:
        return BreakoutResult(FAKE_BREAKOUT, "price broke below support intrabar but closed back above it")
    if candle.close <= support.low - confirmation_buffer:
        return BreakoutResult(TRUE_BREAKOUT, "candle closed clearly below support")
    return BreakoutResult(WAIT, "support was breached but the close is not decisive")


def classify_resistance_breakout(
    candle: Candle,
    resistance: PriceZone,
    confirmation_buffer: float = 0.0002,
) -> BreakoutResult:
    """Classify a move through resistance using the mirrored rules."""
    if resistance.kind != RESISTANCE:
        raise ValueError("zone must be RESISTANCE")
    if confirmation_buffer < 0:
        raise ValueError("confirmation_buffer must be >= 0")

    if candle.high <= resistance.high:
        return BreakoutResult(NO_BREAKOUT, "price did not break above resistance")
    if candle.close <= resistance.high:
        return BreakoutResult(FAKE_BREAKOUT, "price broke above resistance intrabar but closed back below it")
    if candle.close >= resistance.high + confirmation_buffer:
        return BreakoutResult(TRUE_BREAKOUT, "candle closed clearly above resistance")
    return BreakoutResult(WAIT, "resistance was breached but the close is not decisive")


def long_protection(candle: Candle, support: PriceZone, confirmation_buffer: float = 0.0002) -> str:
    """Return WAIT whenever a support fake/uncertain/true break needs filtering."""
    result = classify_support_breakout(candle, support, confirmation_buffer)
    if result.state in {FAKE_BREAKOUT, TRUE_BREAKOUT, WAIT}:
        return WAIT
    return "ALLOW"


def short_protection(candle: Candle, resistance: PriceZone, confirmation_buffer: float = 0.0002) -> str:
    """Return WAIT whenever a resistance fake/uncertain/true break needs filtering."""
    result = classify_resistance_breakout(candle, resistance, confirmation_buffer)
    if result.state in {FAKE_BREAKOUT, TRUE_BREAKOUT, WAIT}:
        return WAIT
    return "ALLOW"
