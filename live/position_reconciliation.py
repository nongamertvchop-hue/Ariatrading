"""Deterministic reconciliation between durable intents and broker positions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isclose, isfinite
from typing import Iterable, Mapping

from live.mt5_executor import PositionSnapshot


class ReconciliationState(str, Enum):
    CLEAN = "CLEAN"
    UNFINISHED = "UNFINISHED"
    MISMATCH = "MISMATCH"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class ReconciliationReport:
    state: ReconciliationState
    reasons: tuple[str, ...]
    matched_intents: int
    observed_positions: int


def reconcile(
    intents: Iterable[Mapping[str, object]],
    positions: Iterable[PositionSnapshot],
    *,
    volume_tolerance: float = 1e-9,
) -> ReconciliationReport:
    """Require every non-terminal intent to map to exactly one owned position.

    Missing, duplicate, or malformed mappings are blocking states. The function
    never assumes that a successful order response is proof of a position.
    """
    if volume_tolerance < 0 or not isfinite(volume_tolerance):
        raise ValueError("volume_tolerance must be finite and non-negative")
    active = [dict(item) for item in intents if str(item.get("state")) in {"RESERVED", "SUBMITTED", "AMBIGUOUS"}]
    observed = list(positions)
    if not active:
        return ReconciliationReport(ReconciliationState.CLEAN, (), 0, len(observed))

    reasons: list[str] = []
    used_tickets: set[int] = set()
    matched = 0
    for intent in active:
        symbol = str(intent.get("symbol", "")).upper()
        direction = str(intent.get("direction", "")).upper()
        raw_volume = intent.get("lot_size")
        try:
            volume = float(raw_volume)
        except (TypeError, ValueError):
            reasons.append("intent has invalid lot_size")
            continue
        if not symbol or direction not in {"BUY", "SELL"} or not isfinite(volume) or volume <= 0:
            reasons.append(f"malformed intent {intent.get('intent_id', '<unknown>')}")
            continue
        matches = [
            position for position in observed
            if position.symbol.upper() == symbol
            and position.order_type.upper() == direction
            and isclose(position.volume, volume, rel_tol=volume_tolerance, abs_tol=volume_tolerance)
        ]
        if len(matches) == 1:
            ticket = matches[0].ticket
            if ticket in used_tickets:
                reasons.append(f"duplicate position match for ticket {ticket}")
            else:
                used_tickets.add(ticket)
                matched += 1
        elif not matches:
            reasons.append(f"no broker position matches intent {intent.get('intent_id', '<unknown>')}")
        else:
            reasons.append(f"multiple broker positions match intent {intent.get('intent_id', '<unknown>')}")

    if any("malformed" in reason for reason in reasons):
        state = ReconciliationState.AMBIGUOUS
    elif any("no broker" in reason or "multiple broker" in reason or "duplicate" in reason for reason in reasons):
        state = ReconciliationState.MISMATCH
    else:
        state = ReconciliationState.UNFINISHED
    return ReconciliationReport(state, tuple(reasons), matched, len(observed))
