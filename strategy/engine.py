"""Unified multi-candle engine for the two basic price-action setups.

The same reversal model works on 1m, 5m, 15m, 30m, 1h, 4h and 1D candles:
APPROACH -> TEST -> RECLAIM/REJECT -> CONFIRM -> LONG/SHORT.

Educational/demo only. No orders are placed here.
"""

from dataclasses import dataclass

from .levels_v2 import PriceZone, SUPPORT, RESISTANCE
from .sequence import evaluate_sequence
from .timeframe import get_timeframe_config

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
    test_index: int | None = None
    confirmation_index: int | None = None


def evaluate_long(candles: list[dict], support: PriceZone, timeframe: str) -> EngineSignal:
    get_timeframe_config(timeframe)
    if support.kind != SUPPORT:
        raise ValueError("zone must be SUPPORT")
    result = evaluate_sequence(candles, support, timeframe, LONG)
    return EngineSignal(
        result.action,
        result.reason,
        timeframe,
        support,
        protection="SAFE" if result.action == LONG else "BLOCKED" if result.state == "BROKEN" else "SAFE",
        breakout_state=result.state,
        entry_reference=result.entry_reference,
        test_index=result.test_index,
        confirmation_index=result.confirmation_index,
    )


def evaluate_short(candles: list[dict], resistance: PriceZone, timeframe: str) -> EngineSignal:
    get_timeframe_config(timeframe)
    if resistance.kind != RESISTANCE:
        raise ValueError("zone must be RESISTANCE")
    result = evaluate_sequence(candles, resistance, timeframe, SHORT)
    return EngineSignal(
        result.action,
        result.reason,
        timeframe,
        resistance,
        protection="SAFE" if result.action == SHORT else "BLOCKED" if result.state == "BROKEN" else "SAFE",
        breakout_state=result.state,
        entry_reference=result.entry_reference,
        test_index=result.test_index,
        confirmation_index=result.confirmation_index,
    )
