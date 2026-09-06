"""Unified timeframe-aware engine for the two basic price-action setups.

The same decision model works on 1m, 5m, 15m, 30m, 1h, 4h and 1D candles.
It is intentionally conservative: incomplete or ambiguous setups return WAIT.
No indicators are required on the chart and no orders are placed.
"""

from dataclasses import dataclass

from .candles import Candle, candle_pressure
from .fake_breakout import (
    FAKE_BREAKOUT,
    TRUE_BREAKOUT,
    WAIT as BREAKOUT_WAIT,
    classify_resistance_breakout,
    classify_support_breakout,
)
from .levels_v2 import PriceZone, SUPPORT, RESISTANCE
from .timeframe import (
    adaptive_confirmation_buffer,
    adaptive_zone_tolerance,
    get_timeframe_config,
)

LONG = "LONG"
SHORT = "SHORT"
WAIT = "WAIT"


@dataclass(frozen=True)
class EngineSignal:
    action: str
    reason: str
    timeframe: str
    zone: PriceZone | None = None
    protection: str = "SAFE"
    breakout_state: str = "NO_BREAKOUT"
    entry_reference: float | None = None


def _candle(raw: dict) -> Candle:
    return Candle(
        open=float(raw["open"]),
        high=float(raw["high"]),
        low=float(raw["low"]),
        close=float(raw["close"]),
    )


def evaluate_long(
    candles: list[dict],
    support: PriceZone,
    timeframe: str,
) -> EngineSignal:
    """Evaluate the latest completed candle at support."""
    get_timeframe_config(timeframe)
    if support.kind != SUPPORT:
        raise ValueError("zone must be SUPPORT")
    if not candles:
        return EngineSignal(WAIT, "no candle data", timeframe, support)

    candle = _candle(candles[-1])
    buffer = adaptive_confirmation_buffer(candles, timeframe)
    zone_tolerance = adaptive_zone_tolerance(candles, timeframe)
    breakout = classify_support_breakout(candle, support, buffer)

    if breakout.state in {FAKE_BREAKOUT, TRUE_BREAKOUT, BREAKOUT_WAIT}:
        return EngineSignal(
            WAIT,
            f"support breakout filter: {breakout.reason}",
            timeframe,
            support,
            protection="BLOCKED",
            breakout_state=breakout.state,
        )

    touches = candle.low <= support.high and candle.high >= support.low
    near_zone = abs(candle.close - support.center) <= max(zone_tolerance, support.high - support.low)
    if not touches or not near_zone:
        return EngineSignal(WAIT, "support has not produced a valid test", timeframe, support)

    if candle.close <= support.high:
        return EngineSignal(WAIT, "support tested but price has not reclaimed the zone", timeframe, support)

    if candle_pressure(candle) != "BUYING":
        return EngineSignal(WAIT, "support held but buying confirmation is insufficient", timeframe, support)

    return EngineSignal(
        LONG,
        "support held and buyers confirmed the move",
        timeframe,
        support,
        protection="SAFE",
        breakout_state="NO_BREAKOUT",
        entry_reference=candle.close,
    )


def evaluate_short(
    candles: list[dict],
    resistance: PriceZone,
    timeframe: str,
) -> EngineSignal:
    """Evaluate the latest completed candle at resistance."""
    get_timeframe_config(timeframe)
    if resistance.kind != RESISTANCE:
        raise ValueError("zone must be RESISTANCE")
    if not candles:
        return EngineSignal(WAIT, "no candle data", timeframe, resistance)

    candle = _candle(candles[-1])
    buffer = adaptive_confirmation_buffer(candles, timeframe)
    zone_tolerance = adaptive_zone_tolerance(candles, timeframe)
    breakout = classify_resistance_breakout(candle, resistance, buffer)

    if breakout.state in {FAKE_BREAKOUT, TRUE_BREAKOUT, BREAKOUT_WAIT}:
        return EngineSignal(
            WAIT,
            f"resistance breakout filter: {breakout.reason}",
            timeframe,
            resistance,
            protection="BLOCKED",
            breakout_state=breakout.state,
        )

    touches = candle.low <= resistance.high and candle.high >= resistance.low
    near_zone = abs(candle.close - resistance.center) <= max(zone_tolerance, resistance.high - resistance.low)
    if not touches or not near_zone:
        return EngineSignal(WAIT, "resistance has not produced a valid test", timeframe, resistance)

    if candle.close >= resistance.low:
        return EngineSignal(WAIT, "resistance tested but price has not rejected the zone", timeframe, resistance)

    if candle_pressure(candle) != "SELLING":
        return EngineSignal(WAIT, "resistance held but selling confirmation is insufficient", timeframe, resistance)

    return EngineSignal(
        SHORT,
        "resistance held and sellers confirmed the move",
        timeframe,
        resistance,
        protection="SAFE",
        breakout_state="NO_BREAKOUT",
        entry_reference=candle.close,
    )
