"""Indicator confirmation for the two core price-action setups.

Indicators are a veto/context layer around the existing APPROACH -> TEST ->
RECLAIM/REJECT -> CONFIRM setup. They never create a trade by themselves.

The filter deliberately uses only the latest completed candle and causal
indicator values. A setup is blocked only when all three directional signals
(EMA20/50 trend, RSI14 regime, MACD line vs signal) oppose the setup. This
keeps the price-action strategy primary while avoiding trades that have a
strongly contradictory momentum/trend context.
"""

from dataclasses import dataclass

from .indicators import IndicatorSnapshot

LONG = "LONG"
SHORT = "SHORT"


@dataclass(frozen=True)
class IndicatorFilterResult:
    allowed: bool
    confirmations: int
    state: str
    reasons: tuple[str, ...]


def evaluate_indicator_filter(
    indicators: IndicatorSnapshot | None,
    direction: str,
) -> IndicatorFilterResult:
    """Return whether indicator context vetoes a confirmed price-action setup."""
    if direction not in {LONG, SHORT}:
        raise ValueError("direction must be LONG or SHORT")
    if indicators is None:
        return IndicatorFilterResult(True, 0, "UNAVAILABLE", ("indicator data unavailable; price-action rule remains primary",))

    bullish = 0
    bearish = 0
    reasons: list[str] = []

    if indicators.ema20 is not None and indicators.ema50 is not None:
        if indicators.ema20 > indicators.ema50:
            bullish += 1
            reasons.append("EMA20 > EMA50")
        elif indicators.ema20 < indicators.ema50:
            bearish += 1
            reasons.append("EMA20 < EMA50")

    if indicators.rsi14 is not None:
        if indicators.rsi14 > 50.0:
            bullish += 1
            reasons.append("RSI14 > 50")
        elif indicators.rsi14 < 50.0:
            bearish += 1
            reasons.append("RSI14 < 50")

    if indicators.macd is not None and indicators.macd_signal is not None:
        if indicators.macd > indicators.macd_signal:
            bullish += 1
            reasons.append("MACD > signal")
        elif indicators.macd < indicators.macd_signal:
            bearish += 1
            reasons.append("MACD < signal")

    opposing = bearish if direction == LONG else bullish
    supporting = bullish if direction == LONG else bearish
    allowed = opposing < 3
    state = "SUPPORTIVE" if supporting > opposing else "MIXED" if supporting == opposing else "OPPOSED"
    if not reasons:
        reasons.append("indicator values are not warmed up")

    return IndicatorFilterResult(allowed, supporting, state, tuple(reasons))
