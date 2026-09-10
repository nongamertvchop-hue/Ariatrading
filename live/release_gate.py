"""Machine-checkable release gate for progression from DEMO to LIVE.

Some readiness items can be proven from code/tests; others require broker/demo
soak evidence. The gate deliberately refuses LIVE unless every item is marked
true by the operator/evidence pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


READINESS_ITEMS = tuple(range(1, 51))


@dataclass(frozen=True)
class ReadinessDecision:
    ready: bool
    missing: tuple[int, ...]
    reason: str


def evaluate_readiness(evidence: Mapping[int, bool]) -> ReadinessDecision:
    missing = tuple(item for item in READINESS_ITEMS if evidence.get(item) is not True)
    if missing:
        return ReadinessDecision(
            ready=False,
            missing=missing,
            reason=f"live release blocked: {len(missing)} readiness items are not proven",
        )
    return ReadinessDecision(ready=True, missing=(), reason="all 50 readiness items are explicitly proven")


def require_live_readiness(evidence: Mapping[int, bool]) -> None:
    """Raise instead of guessing when LIVE evidence is incomplete."""
    decision = evaluate_readiness(evidence)
    if not decision.ready:
        raise RuntimeError(f"{decision.reason}; missing={','.join(map(str, decision.missing))}")
