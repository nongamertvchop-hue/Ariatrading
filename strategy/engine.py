"""Unified engine for the two basic price-action setups.

Core setup:
APPROACH -> TEST -> RECLAIM/REJECT -> CONFIRM -> LONG/SHORT.

Market structure and setup scoring are context layers. Indicators now act as
an explicit directional confirmation layer for the two existing directions;
they still cannot create a third direction.

All indicator inputs are completed candles only. No future candle is used.

Educational/demo only. No orders are placed here.
The runtime research contract is enforced on every evaluation.
"""

from dataclasses import dataclass

from .indicators import IndicatorSnapshot, calculate_indicators
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
    indicators: IndicatorSnapshot | None = None


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


def _indicator_confirmation(
    direction: str,
    indicators: IndicatorSnapshot,
) -> tuple[bool, int, tuple[str, ...]]:
    """Confirm an existing price-action direction with causal indicators.

    Direction comes from the price-action sequence first. Indicators only
    confirm or block that direction; they never create LONG/SHORT by
    themselves. EMA20/50, RSI14 and MACD histogram are the minimum directional
    evidence set. EMA50/200 is an additional higher-confidence trend check
    when warmed up. ADX measures trend strength but is not directional.
    """
    checks: list[bool] = []
    reasons: list[str] = []

    if indicators.ema20 is not None and indicators.ema50 is not None:
        bullish = indicators.ema20 > indicators.ema50
        aligned = bullish if direction == LONG else not bullish
        checks.append(aligned)
        reasons.append("EMA20/50=" + ("aligned" if aligned else "opposed"))

    if indicators.rsi14 is not None:
        aligned = indicators.rsi14 >= 50.0 if direction == LONG else indicators.rsi14 <= 50.0
        checks.append(aligned)
        reasons.append(f"RSI14={indicators.rsi14:.2f}" + (" aligned" if aligned else " opposed"))

    if indicators.macd_histogram is not None:
        aligned = indicators.macd_histogram >= 0.0 if direction == LONG else indicators.macd_histogram <= 0.0
        checks.append(aligned)
        reasons.append("MACD histogram=" + ("aligned" if aligned else "opposed"))

    if indicators.ema50 is not None and indicators.ema200 is not None:
        aligned = indicators.ema50 > indicators.ema200 if direction == LONG else indicators.ema50 < indicators.ema200
        checks.append(aligned)
        reasons.append("EMA50/200=" + ("aligned" if aligned else "opposed"))

    if not checks:
        return False, 0, ("indicator warmup incomplete",)

    # The minimum live lookback normally supplies EMA20/50 + RSI + MACD.
    # Require every available directional check so a conflicting indicator
    # cannot silently approve the opposite price-action setup.
    aligned_count = sum(checks)
    all_aligned = aligned_count == len(checks)

    adx_bonus = 0
    if indicators.adx14 is not None:
        if indicators.adx14 >= 25.0:
            adx_bonus = 2
            reasons.append(f"ADX14={indicators.adx14:.2f} strong")
        elif indicators.adx14 >= 20.0:
            adx_bonus = 1
            reasons.append(f"ADX14={indicators.adx14:.2f} moderate")
        else:
            reasons.append(f"ADX14={indicators.adx14:.2f} weak")

    strength = min(20, 18 + adx_bonus) if all_aligned else 0
    return all_aligned, strength, tuple(reasons)


def _evaluate(
    candles: list[dict],
    zone: PriceZone,
    timeframe: str,
    direction: str,
    mtf: MultiTimeframeContext | None,
    max_test_age: int,
) -> EngineSignal:
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
    # The latest candle is already closed when this engine is called. It is
    # valid indicator input; no future candle is consulted.
    indicators = calculate_indicators(candles) if candles else None
    setup_score = None
    stop_reference = None

    if result.action == direction:
        if indicators is None:
            return EngineSignal(
                WAIT,
                "indicator confirmation unavailable",
                timeframe,
                zone=zone,
                protection="BLOCKED",
                breakout_state=result.breakout_state,
                entry_reference=result.entry_reference,
                test_index=result.test_index,
                confirmation_index=result.confirmation_index,
                structure_bias=structure.bias,
                state=result.state,
                indicators=None,
            )

        confirmed, confirmation_strength, indicator_reasons = _indicator_confirmation(direction, indicators)
        if not confirmed:
            return EngineSignal(
                WAIT,
                "indicator confirmation blocked " + direction + ": " + "; ".join(indicator_reasons),
                timeframe,
                zone=zone,
                protection="BLOCKED",
                breakout_state=result.breakout_state,
                entry_reference=result.entry_reference,
                test_index=result.test_index,
                confirmation_index=result.confirmation_index,
                structure_bias=structure.bias,
                state=result.state,
                indicators=indicators,
            )

        setup_score = score_setup(
            direction=direction,
            zone_touches=zone.touches,
            structure=structure,
            breakout_state=result.breakout_state,
            confirmation_strength=confirmation_strength,
            mtf=mtf,
        )
        stop_reference = _protective_stop(zone, direction, candles[:-1], timeframe)
        reason = result.reason + "; indicators confirmed " + direction
    else:
        reason = result.reason

    return EngineSignal(
        result.action if result.action == direction else WAIT,
        reason,
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
        indicators=indicators,
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
