"""Transparent setup-quality scoring for the two core price-action setups.

The score is a heuristic ranking tool, not a probability of winning. Its main
purpose is to make the reasons behind a setup explicit and testable.

Maximum score: 100.

Educational research only. No orders are placed here.
"""

from dataclasses import dataclass

from .market_structure import BEARISH, BULLISH, MarketStructure
from .mtf import MultiTimeframeContext


@dataclass(frozen=True)
class SetupScore:
    total: int
    zone: int
    structure: int
    breakout: int
    confirmation: int
    mtf: int
    reasons: tuple[str, ...]


def score_setup(
    direction: str,
    zone_touches: int,
    structure: MarketStructure,
    breakout_state: str,
    confirmation_strength: int,
    mtf: MultiTimeframeContext | None = None,
) -> SetupScore:
    """Score a completed setup using deterministic, explainable components."""
    if direction not in {"LONG", "SHORT"}:
        raise ValueError("direction must be LONG or SHORT")
    if zone_touches < 0:
        raise ValueError("zone_touches must be >= 0")
    if not 0 <= confirmation_strength <= 20:
        raise ValueError("confirmation_strength must be between 0 and 20")

    zone = min(25, zone_touches * 5)
    expected = BULLISH if direction == "LONG" else BEARISH
    structure_points = 20 if structure.bias == expected else 0

    # A clean rejection is useful evidence; a fake breakout is useful too,
    # but is deliberately capped lower because it is a more volatile pattern.
    if breakout_state == "NO_BREAKOUT":
        breakout = 20
    elif breakout_state == "FAKE_BREAKOUT":
        breakout = 25
    elif breakout_state == "WAIT":
        breakout = 0
    else:
        breakout = 0

    mtf_points = 0 if mtf is None else (10 if (
        (direction == "LONG" and mtf.alignment == BULLISH)
        or (direction == "SHORT" and mtf.alignment == BEARISH)
    ) else 0)

    reasons: list[str] = []
    reasons.append(f"zone touches={zone_touches}: {zone}/25")
    reasons.append(f"structure={structure.bias}: {structure_points}/20")
    reasons.append(f"breakout={breakout_state}: {breakout}/25")
    reasons.append(f"confirmation={confirmation_strength}/20")
    reasons.append(f"mtf={mtf.alignment if mtf else 'UNAVAILABLE'}: {mtf_points}/10")

    total = zone + structure_points + breakout + confirmation_strength + mtf_points
    return SetupScore(total, zone, structure_points, breakout, confirmation_strength, mtf_points, tuple(reasons))
