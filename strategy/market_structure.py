"""Indicator-free market-structure analysis built from confirmed swings.

The module labels confirmed swing highs/lows as HH, HL, LH, or LL and derives
an intentionally simple bullish/bearish/range/unknown bias. A directional
bias requires at least two confirmed highs and two confirmed lows.

Educational research only. No orders are placed here.
"""

from dataclasses import dataclass

from .levels_v2 import confirmed_swing_highs, confirmed_swing_lows

BULLISH = "BULLISH"
BEARISH = "BEARISH"
RANGE = "RANGE"
UNKNOWN = "UNKNOWN"

HH = "HH"
HL = "HL"
LH = "LH"
LL = "LL"


@dataclass(frozen=True)
class StructurePoint:
    index: int
    price: float
    kind: str


@dataclass(frozen=True)
class MarketStructure:
    bias: str
    highs: tuple[StructurePoint, ...]
    lows: tuple[StructurePoint, ...]
    points: tuple[StructurePoint, ...]


def analyze_market_structure(candles: list[dict], strength: int = 2) -> MarketStructure:
    """Analyze confirmed swing structure without using future candles."""
    raw_highs = confirmed_swing_highs(candles, strength)
    raw_lows = confirmed_swing_lows(candles, strength)

    highs: list[StructurePoint] = []
    lows: list[StructurePoint] = []

    for index, price in raw_highs:
        kind = HH if not highs or price > highs[-1].price else LH
        highs.append(StructurePoint(index, price, kind))

    for index, price in raw_lows:
        kind = HL if not lows or price > lows[-1].price else LL
        lows.append(StructurePoint(index, price, kind))

    points = tuple(sorted((*highs, *lows), key=lambda p: p.index))
    if len(highs) < 2 or len(lows) < 2:
        bias = UNKNOWN
    elif highs[-1].kind == HH and lows[-1].kind == HL:
        bias = BULLISH
    elif highs[-1].kind == LH and lows[-1].kind == LL:
        bias = BEARISH
    else:
        bias = RANGE

    return MarketStructure(bias, tuple(highs), tuple(lows), points)


def direction_is_aligned(direction: str, structure: MarketStructure) -> bool:
    """Return whether a LONG/SHORT direction agrees with structure bias."""
    if direction == "LONG":
        return structure.bias == BULLISH
    if direction == "SHORT":
        return structure.bias == BEARISH
    raise ValueError("direction must be LONG or SHORT")
