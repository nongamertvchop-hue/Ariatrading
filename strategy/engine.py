"""Unified engine for the two basic price-action setups.

Core setup:
APPROACH -> TEST -> RECLAIM/REJECT -> CONFIRM -> LONG/SHORT.

Market structure and setup scoring are context layers. They do not create a
third setup and do not turn a score into a win probability.

Educational/demo only. No orders are placed here.
The runtime research contract is enforced on every evaluation.
"""

from dataclasses import dataclass

from .levels_v2 import PriceZone, SUPPORT, RESISTANCE
from .market_structure import MarketStructure, analyze_market_structure
from .mtf import MultiTimeframeContext
from .research_rules import enforce_research_contract
from .scoring import SetupScore, score_setup
from .sequence import evaluate_sequence
from .timeframe import adaptive_confirmation_buffer, get_timeframe_config

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
    stop_reference: float | None = None
    test_index: int | None = None
    confirmation_index: int | None = None
    structure_bias: str = "UNKNOWN"
    score: SetupScore | None = None
    state: str = "APPROACH"


def _protective_stop(
    zone: PriceZone,
    direction: str,
    candles: list[dict],
    timeframe: str,
) -> float:
    """Place the strategy's protective stop beyond the reaction zone.

    The distance adapts to recent candle ranges, so the same price-action rule
    can operate across 1m through 1D without introducing an indicator.
    """
    buffer = adaptive_confirmation_buffer(candles, timeframe)
    if direction == LONG:
        return zone.low - buffer
    if direction == SHORT:
        return zone.high + buffer
    raise ValueError("direction must be LONG or SHORT")


def _evaluate(
    candles: list[dict],
    zone: PriceZone,
    timeframe: str,
    direction: str,
    mtf: MultiTimeframeContext | None,
    max_test_age: int,
) -> EngineSignal:
    # The research contract is deliberately checked at the strategy boundary:
    # new research can evolve, but execution mode and causal-data safeguards
    # cannot silently drift while experiments are being developed.
    enforce_research_contract()

    get_timeframe_config(timeframe)
    result = evaluate_sequence(
        candles,
        zone,
        timeframe,
        direction,
        max_test_age=max_test_age,
    )
    structure = analyze_market_structure(candles[:-1]) if len(candles) > 1 else analyze_market_structure([])
    setup_score = None
    stop_reference = None
    if result.action == direction:
        setup_score = score_setup(
            direction=direction,
            zone_touches=zone.touches,
            structure=structure,
            breakout_state=result.breakout_state,
            confirmation_strength=20,
            mtf=mtf,
        )
        stop_reference = _protective_stop(zone, direction, candles[:-1], timeframe)

    return EngineSignal(
        result.action,
        result.reason,
        timeframe,
        zone,
        protection="SAFE" if result.action == direction else "BLOCKED" if result.state == "BROKEN" else "SAFE",
        breakout_state=result.breakout_state,
        entry_reference=result.entry_reference,
        stop_reference=stop_reference,
        test_index=result.test_index,
        confirmation_index=result.confirmation_index,
        structure_bias=structure.bias,
        score=setup_score,
        state=result.state,
    )


def evaluate_long(
    candles: list[dict],
    support: PriceZone,
    timeframe: str,
    mtf: MultiTimeframeContext | None = None,
    max_test_age: int = 3,
) -> EngineSignal:
    if support.kind != SUPPORT:
        raise ValueError("zone must be SUPPORT")
    return _evaluate(candles, support, timeframe, LONG, mtf, max_test_age)


def evaluate_short(
    candles: list[dict],
    resistance: PriceZone,
    timeframe: str,
    mtf: MultiTimeframeContext | None = None,
    max_test_age: int = 3,
) -> EngineSignal:
    if resistance.kind != RESISTANCE:
        raise ValueError("zone must be RESISTANCE")
    return _evaluate(candles, resistance, timeframe, SHORT, mtf, max_test_age)
