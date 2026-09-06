"""Multi-timeframe context for the two core support/resistance setups.

This layer does not create a new entry setup. It only describes whether the
available higher/middle timeframe structures agree with an entry direction.

Educational research only. No orders are placed here.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .market_structure import BEARISH, BULLISH, MarketStructure, RANGE, UNKNOWN, analyze_market_structure
from .timeframe import SUPPORTED_TIMEFRAMES


@dataclass(frozen=True)
class MultiTimeframeContext:
    entry_timeframe: str
    higher_bias: str
    middle_bias: str
    entry_bias: str
    alignment: str


_ORDER = {name: i for i, name in enumerate(SUPPORTED_TIMEFRAMES)}
_DURATION = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1D": timedelta(days=1),
}


def bar_duration(timeframe: str) -> timedelta:
    """Return the fixed candle duration used for timestamp alignment."""
    try:
        return _DURATION[timeframe]
    except KeyError as exc:
        raise ValueError(f"unsupported timeframe: {timeframe}") from exc


def build_mtf_context(
    structures: dict[str, MarketStructure],
    entry_timeframe: str,
) -> MultiTimeframeContext:
    """Build context from structures already calculated on closed candles."""
    if entry_timeframe not in _ORDER:
        raise ValueError(f"unsupported timeframe: {entry_timeframe}")

    entry = structures.get(entry_timeframe)
    entry_bias = UNKNOWN if entry is None else entry.bias

    higher = [
        (tf, s.bias)
        for tf, s in structures.items()
        if tf in _ORDER and _ORDER[tf] > _ORDER[entry_timeframe]
    ]
    higher.sort(key=lambda item: _ORDER[item[0]])

    middle_bias = RANGE
    if higher:
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


def _bar_time(bar: dict) -> datetime:
    value = bar["time"]
    if not isinstance(value, datetime):
        raise TypeError("candle time must be a datetime")
    if value.tzinfo is None:
        raise ValueError("candle time must be timezone-aware")
    return value


def closed_candles_at(
    candles: list[dict],
    timeframe: str,
    timestamp: datetime,
) -> list[dict]:
    """Return only candles whose full interval closed by ``timestamp``.

    MT5 timestamps represent the candle opening time. Therefore a higher
    timeframe candle that opened before an entry is not automatically usable:
    its own close must be at or before the entry timestamp. This prevents
    higher-timeframe look-ahead bias in historical validation.
    """
    duration = bar_duration(timeframe)
    if timestamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")

    ordered = sorted(candles, key=_bar_time)
    return [
        bar for bar in ordered
        if _bar_time(bar) + duration <= timestamp
    ]


def build_timestamp_aligned_mtf_context(
    candles_by_timeframe: dict[str, list[dict]],
    entry_timeframe: str,
    entry_timestamp: datetime,
    strength: int = 2,
) -> MultiTimeframeContext:
    """Build MTF context using only bars fully closed by the entry timestamp.

    ``entry_timestamp`` is the close time of the signal candle. All timeframe
    structures are independently truncated before analysis, so a future
    higher-timeframe candle can never influence the signal.
    """
    if entry_timeframe not in _ORDER:
        raise ValueError(f"unsupported timeframe: {entry_timeframe}")

    structures: dict[str, MarketStructure] = {}
    for timeframe, candles in candles_by_timeframe.items():
        if timeframe not in _ORDER:
            continue
        closed = closed_candles_at(candles, timeframe, entry_timestamp)
        structures[timeframe] = analyze_market_structure(closed, strength=strength)

    return build_mtf_context(structures, entry_timeframe)


def mtf_direction_score(direction: str, context: MultiTimeframeContext) -> int:
    """Return a small heuristic context score; this is not win probability."""
    if direction == "LONG":
        return 10 if context.alignment == BULLISH else 0
    if direction == "SHORT":
        return 10 if context.alignment == BEARISH else 0
    raise ValueError("direction must be LONG or SHORT")
