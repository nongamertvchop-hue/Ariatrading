"""Multi-timeframe context for the two core support/resistance setups.

This layer does not create a new entry setup. It only describes whether the
available higher/middle timeframe structures agree with an entry direction.

Educational research only. No orders are placed here.
"""

from dataclasses import dataclass

from .market_structure import BEARISH, BULLISH, MarketStructure, RANGE, UNKNOWN
from .timeframe import SUPPORTED_TIMEFRAMES


@dataclass(frozen=True)
class MultiTimeframeContext:
    entry_timeframe: str
    higher_bias: str
    middle_bias: str
    entry_bias: str
    alignment: str


_ORDER = {name: i for i, name in enumerate(SUPPORTED_TIMEFRAMES)}


def build_mtf_context(
    structures: dict[str, MarketStructure],
    entry_timeframe: str,
) -> MultiTimeframeContext:
    """Build context from structures already calculated on closed candles."""
    if entry_timeframe not in _ORDER:
        raise ValueError(f"unsupported timeframe: {entry_timeframe}")

    entry = structures.get(entry_timeframe)
    if entry is None:
        entry_bias = UNKNOWN
    else:
        entry_bias = entry.bias

    higher = [
        (tf, s.bias)
        for tf, s in structures.items()
        if tf in _ORDER and _ORDER[tf] > _ORDER[entry_timeframe]
    ]
    higher.sort(key=lambda item: _ORDER[item[0]])

    middle_bias = RANGE
    if higher:
        # The closest higher timeframe is the middle/context layer.
        middle_bias = higher[0][1]
    higher_bias = higher[-1][1] if higher else UNKNOWN

    biases = [b for b in (higher_bias, middle_bias, entry_bias) if b not in {UNKNOWN, RANGE}]
    if len(biases) >= 2 and all(b == BULLISH for b in biases):
        alignment = BULLISH
    elif len(biases) >= 2 and all(b == BEARISH for b in biases):
        alignment = BEARISH
    elif biases:
        alignment = RANGE
    else:
        alignment = UNKNOWN

    return MultiTimeframeContext(
        entry_timeframe,
        higher_bias,
        middle_bias,
        entry_bias,
        alignment,
    )


def mtf_direction_score(direction: str, context: MultiTimeframeContext) -> int:
    """Return a small heuristic context score; this is not win probability."""
    if direction == "LONG":
        return 10 if context.alignment == BULLISH else 0
    if direction == "SHORT":
        return 10 if context.alignment == BEARISH else 0
    raise ValueError("direction must be LONG or SHORT")
