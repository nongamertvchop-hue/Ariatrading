"""Final consistency gate for realtime research decisions.

The supervisor does not create a new setup. It only decides whether an already
computed LONG/SHORT setup is sufficiently coherent to expose as an actionable
research state. Any unresolved conflict becomes WAIT.

Research/paper monitoring only. No broker orders are placed here.
"""

from dataclasses import dataclass

from .engine import EngineSignal, LONG, SHORT, WAIT
from .forecast import DOWN, UP, ForecastResult
from .mtf import BEARISH, BULLISH, MultiTimeframeContext

ALLOW = "ALLOW"


@dataclass(frozen=True)
class SupervisorDecision:
    action: str
    allowed: bool
    reasons: tuple[str, ...]


def supervise(
    signal: EngineSignal,
    forecast_result: ForecastResult | None = None,
    mtf: MultiTimeframeContext | None = None,
    min_confidence: float = 0.45,
) -> SupervisorDecision:
    """Apply deterministic consistency checks to a realtime strategy result."""
    if not 0.0 <= min_confidence <= 1.0:
        raise ValueError("min_confidence must be between 0 and 1")

    reasons: list[str] = []
    if signal.action == WAIT:
        return SupervisorDecision(WAIT, False, ("strategy is WAIT",))
    if signal.action not in {LONG, SHORT}:
        return SupervisorDecision(WAIT, False, ("unknown strategy action",))

    if signal.protection != "SAFE":
        reasons.append("protection is not SAFE")
    if signal.breakout_state not in {"NO_BREAKOUT", ""}:
        reasons.append(f"breakout state is {signal.breakout_state}")

    if forecast_result is None:
        reasons.append("forecast unavailable")
    else:
        if forecast_result.confidence < min_confidence:
            reasons.append("forecast confidence below threshold")
        first = forecast_result.horizons[0] if forecast_result.horizons else None
        if first is None:
            reasons.append("forecast horizon unavailable")
        elif signal.action == LONG and first.direction == DOWN:
            reasons.append("LONG conflicts with near-horizon DOWN forecast")
        elif signal.action == SHORT and first.direction == UP:
            reasons.append("SHORT conflicts with near-horizon UP forecast")

    if mtf is not None:
        if signal.action == LONG and mtf.alignment == BEARISH:
            reasons.append("LONG conflicts with bearish MTF alignment")
        elif signal.action == SHORT and mtf.alignment == BULLISH:
            reasons.append("SHORT conflicts with bullish MTF alignment")

    if reasons:
        return SupervisorDecision(WAIT, False, tuple(reasons))
    return SupervisorDecision(ALLOW, True, ("all realtime consistency checks passed",))
