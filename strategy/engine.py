"""Unified engine for the two basic price-action setups.

Core setup:
APPROACH -> TEST -> RECLAIM/REJECT -> CONFIRM -> LONG/SHORT.

Market structure and setup scoring are context layers. They do not create a
third setup and do not turn a score into a win probability.

Educational/demo only. No orders are placed here.
"""

from dataclasses import dataclass

from .levels_v2 import PriceZone, SUPPORT, RESISTANCE
from .market_structure import MarketStructure, analyze_market_structure
from .mtf import MultiTimeframeContext
from .scoring import SetupScore, score_setup
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
    structure_bias: str = "UNKNOWN"
    score: SetupScore | None = None


def _evaluate(candles: list[dict], zone: PriceZone, timeframe: str, direction: str, mtf: MultiTimeframeContext | None) -> EngineSignal:
    get_timeframe_config(timeframe)
    result = evaluate_sequence(candles, zone, timeframe, direction)
    structure = analyze_market_structure(candles[:-1]) if len(candles) > 1 else analyze_market_structure([])
    setup_score = None
    if result.action == direction:
        setup_score = score_setup(
            direction=direction,
            zone_touches=zone.touches,
            structure=structure,
            breakout_state=result.breakout_state,
            confirmation_strength=20,
            mtf=mtf,
        )

    return EngineSignal(
        result.action,
        result.reason,
        timeframe,
        zone,
        protection="SAFE" if result.action == direction else "BLOCKED" if result.state == "BROKEN" else "SAFE",
        breakout_state=result.breakout_state,
        entry_reference=result.entry_reference,
        test_index=result.test_index,
        confirmation_index=result.confirmation_index,
        structure_bias=structure.bias,
        score=setup_score,
    )


def evaluate_long(
    candles: list[dict],
    support: PriceZone,
    timeframe: str,
    mtf: MultiTimeframeContext | None = None,
) -> EngineSignal:
    if support.kind != SUPPORT:
        raise ValueError("zone must be SUPPORT")
    return _evaluate(candles, support, timeframe, LONG, mtf)


def evaluate_short(
    candles: list[dict],
    resistance: PriceZone,
    timeframe: str,
    mtf: MultiTimeframeContext | None = None,
) -> EngineSignal:
    if resistance.kind != RESISTANCE:
        raise ValueError("zone must be RESISTANCE")
    return _evaluate(candles, resistance, timeframe, SHORT, mtf)
