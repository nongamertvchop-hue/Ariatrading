"""Directional confirmation rules for the indicator layer.

Indicators do not create a trade direction. They validate an already-confirmed
price-action LONG/SHORT candidate. The rules use only the latest completed
indicator snapshot, so they remain causal for realtime execution and walk-forward
research.
"""

from __future__ import annotations

from dataclasses import dataclass

from .indicators import IndicatorSnapshot

LONG = "LONG"
SHORT = "SHORT"


@dataclass(frozen=True)
class IndicatorConfirmation:
    allowed: bool
    direction: str
    score: int
    reasons: tuple[str, ...]


def _votes(snapshot: IndicatorSnapshot, direction: str) -> tuple[list[bool], list[str]]:
    votes: list[bool] = []
    reasons: list[str] = []

    if snapshot.ema20 is not None and snapshot.ema50 is not None:
        ok = snapshot.ema20 > snapshot.ema50 if direction == LONG else snapshot.ema20 < snapshot.ema50
        votes.append(ok)
        reasons.append("EMA20/50 aligned" if ok else "EMA20/50 conflict")

    if snapshot.rsi14 is not None:
        ok = snapshot.rsi14 >= 50.0 if direction == LONG else snapshot.rsi14 <= 50.0
        votes.append(ok)
        reasons.append("RSI directional" if ok else "RSI conflict")

    if snapshot.macd_histogram is not None:
        ok = snapshot.macd_histogram >= 0.0 if direction == LONG else snapshot.macd_histogram <= 0.0
        votes.append(ok)
        reasons.append("MACD histogram aligned" if ok else "MACD histogram conflict")

    if snapshot.ema200 is not None and snapshot.ema50 is not None:
        ok = snapshot.ema50 > snapshot.ema200 if direction == LONG else snapshot.ema50 < snapshot.ema200
        votes.append(ok)
        reasons.append("EMA50/200 trend aligned" if ok else "EMA50/200 trend conflict")

    return votes, reasons


def confirm_indicator_direction(
    snapshot: IndicatorSnapshot | None,
    direction: str,
    *,
    minimum_votes: int = 2,
) -> IndicatorConfirmation:
    """Confirm a price-action direction with deterministic indicator evidence."""
    if direction not in {LONG, SHORT}:
        raise ValueError("direction must be LONG or SHORT")
    if minimum_votes < 1:
        raise ValueError("minimum_votes must be >= 1")
    if snapshot is None:
        return IndicatorConfirmation(False, direction, 0, ("indicator snapshot unavailable",))

    votes, reasons = _votes(snapshot, direction)
    if not votes:
        return IndicatorConfirmation(False, direction, 0, ("indicator warmup incomplete",))

    passed = sum(votes)
    required = min(minimum_votes, len(votes))
    score = int(round(100 * passed / len(votes)))
    allowed = passed >= required
    return IndicatorConfirmation(allowed, direction, score, tuple(reasons))
