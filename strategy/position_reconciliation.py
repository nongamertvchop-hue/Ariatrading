"""Deterministic position-state reconciliation for live trading safety.

This module does not place, modify, or close orders. It compares the strategy's
local position state with an externally supplied broker snapshot and fails
closed on ambiguity, duplicates, direction mismatches, or quantity mismatches.
The core LONG/SHORT strategy is intentionally untouched.
"""

from dataclasses import dataclass
from math import isfinite

LONG = "LONG"
SHORT = "SHORT"
FLAT = "FLAT"
ALLOW = "ALLOW"
HALT = "HALT"


@dataclass(frozen=True)
class PositionSnapshot:
    """Minimal normalized position representation used by reconciliation."""

    symbol: str
    direction: str
    quantity: float
    position_id: str

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if self.direction not in {LONG, SHORT}:
            raise ValueError("direction must be LONG or SHORT")
        if not isfinite(self.quantity) or self.quantity <= 0:
            raise ValueError("quantity must be finite and > 0")
        if not self.position_id:
            raise ValueError("position_id must not be empty")


@dataclass(frozen=True)
class LocalPositionState:
    symbol: str
    direction: str
    quantity: float
    position_id: str

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if self.direction not in {LONG, SHORT}:
            raise ValueError("direction must be LONG or SHORT")
        if not isfinite(self.quantity) or self.quantity <= 0:
            raise ValueError("quantity must be finite and > 0")
        if not self.position_id:
            raise ValueError("position_id must not be empty")


@dataclass(frozen=True)
class ReconciliationDecision:
    action: str
    safe: bool
    reason: str
    broker_count: int


def reconcile_position(
    local: LocalPositionState | None,
    broker_positions: list[PositionSnapshot],
    *,
    quantity_tolerance: float = 1e-12,
) -> ReconciliationDecision:
    """Require local and broker position state to agree before new execution."""
    if quantity_tolerance < 0 or not isfinite(quantity_tolerance):
        raise ValueError("quantity_tolerance must be finite and >= 0")

    if len({position.position_id for position in broker_positions}) != len(broker_positions):
        return ReconciliationDecision(HALT, False, "duplicate broker position id detected", len(broker_positions))

    if local is None:
        if not broker_positions:
            return ReconciliationDecision(ALLOW, True, "local and broker are both flat", 0)
        return ReconciliationDecision(HALT, False, "broker has position but local state is flat", len(broker_positions))

    if not broker_positions:
        return ReconciliationDecision(HALT, False, "local state has position but broker is flat", 0)

    if len(broker_positions) != 1:
        return ReconciliationDecision(HALT, False, "multiple broker positions found for single-position strategy", len(broker_positions))

    broker = broker_positions[0]
    if broker.symbol != local.symbol:
        return ReconciliationDecision(HALT, False, "broker symbol differs from local state", 1)
    if broker.position_id != local.position_id:
        return ReconciliationDecision(HALT, False, "broker position id differs from local state", 1)
    if broker.direction != local.direction:
        return ReconciliationDecision(HALT, False, "broker direction differs from local state", 1)
    if abs(broker.quantity - local.quantity) > quantity_tolerance:
        return ReconciliationDecision(HALT, False, "broker quantity differs from local state", 1)

    return ReconciliationDecision(ALLOW, True, "local and broker position state reconciled", 1)


def new_entry_allowed(
    local: LocalPositionState | None,
    broker_positions: list[PositionSnapshot],
    *,
    quantity_tolerance: float = 1e-12,
) -> ReconciliationDecision:
    """Only permit a new entry when both sides agree that the account is flat."""
    decision = reconcile_position(
        local,
        broker_positions,
        quantity_tolerance=quantity_tolerance,
    )
    if not decision.safe:
        return decision
    if local is not None or broker_positions:
        return ReconciliationDecision(
            HALT,
            False,
            "new entry blocked because an existing position is present",
            decision.broker_count,
        )
    return decision
