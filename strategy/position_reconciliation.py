"""Deterministic position-state reconciliation for live trading safety.

This module does not place, modify, or close orders. It compares the strategy's
local position state with an externally supplied broker snapshot and fails
closed on ambiguity, duplicates, direction mismatches, quantity mismatches,
average-entry mismatches, or broker-contract violations.
The core LONG/SHORT strategy is intentionally untouched.
"""

from dataclasses import dataclass
from math import isclose, isfinite

from .broker_contract import SymbolContract, validate_order_contract

LONG = "LONG"
SHORT = "SHORT"
FLAT = "FLAT"
ALLOW = "ALLOW"
HALT = "HALT"


@dataclass(frozen=True)
class PositionSnapshot:
    """Normalized position representation used by reconciliation.

    ``average_entry_price`` is optional for backward compatibility with older
    paper/research snapshots. When both local and broker states provide it,
    reconciliation requires the values to agree within the configured
    tolerance.
    """

    symbol: str
    direction: str
    quantity: float
    position_id: str
    average_entry_price: float | None = None

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if self.direction not in {LONG, SHORT}:
            raise ValueError("direction must be LONG or SHORT")
        if not isfinite(self.quantity) or self.quantity <= 0:
            raise ValueError("quantity must be finite and > 0")
        if not self.position_id:
            raise ValueError("position_id must not be empty")
        if self.average_entry_price is not None and (
            not isfinite(self.average_entry_price) or self.average_entry_price <= 0
        ):
            raise ValueError("average_entry_price must be finite and > 0 when provided")


@dataclass(frozen=True)
class LocalPositionState:
    symbol: str
    direction: str
    quantity: float
    position_id: str
    average_entry_price: float | None = None

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if self.direction not in {LONG, SHORT}:
            raise ValueError("direction must be LONG or SHORT")
        if not isfinite(self.quantity) or self.quantity <= 0:
            raise ValueError("quantity must be finite and > 0")
        if not self.position_id:
            raise ValueError("position_id must not be empty")
        if self.average_entry_price is not None and (
            not isfinite(self.average_entry_price) or self.average_entry_price <= 0
        ):
            raise ValueError("average_entry_price must be finite and > 0 when provided")


@dataclass(frozen=True)
class ReconciliationDecision:
    action: str
    safe: bool
    reason: str
    broker_count: int


def _validate_contract_position(
    position: PositionSnapshot,
    contract: SymbolContract,
) -> str | None:
    """Return a fail-closed reason when a broker position violates its contract."""
    if position.symbol != contract.symbol:
        return "broker position symbol differs from broker contract"

    quantity = position.quantity
    if quantity < contract.volume_min:
        return "broker position violates symbol contract: quantity is below broker minimum"
    if quantity > contract.volume_max:
        return "broker position violates symbol contract: quantity exceeds broker maximum"

    steps = (quantity - contract.volume_min) / contract.volume_step
    if not isclose(steps, round(steps), rel_tol=0.0, abs_tol=1e-9):
        return "broker position violates symbol contract: quantity does not match broker volume step"

    if position.average_entry_price is not None:
        validation = validate_order_contract(
            contract,
            symbol=position.symbol,
            price=position.average_entry_price,
            quantity=quantity,
        )
        if not validation.allowed:
            return "broker position violates symbol contract: " + validation.reason

    return None


def reconcile_position(
    local: LocalPositionState | None,
    broker_positions: list[PositionSnapshot],
    *,
    quantity_tolerance: float = 1e-12,
    price_tolerance: float = 1e-12,
    broker_contract: SymbolContract | None = None,
) -> ReconciliationDecision:
    """Require local and broker position state to agree before new execution.

    Contract validation is optional so existing research callers remain
    backward compatible. When supplied, every broker position must satisfy the
    normalized symbol/volume contract. Average-entry price precision is also
    checked when the broker supplies that value.
    """
    if quantity_tolerance < 0 or not isfinite(quantity_tolerance):
        raise ValueError("quantity_tolerance must be finite and >= 0")
    if price_tolerance < 0 or not isfinite(price_tolerance):
        raise ValueError("price_tolerance must be finite and >= 0")

    if len({position.position_id for position in broker_positions}) != len(broker_positions):
        return ReconciliationDecision(HALT, False, "duplicate broker position id detected", len(broker_positions))

    if broker_contract is not None:
        for position in broker_positions:
            reason = _validate_contract_position(position, broker_contract)
            if reason is not None:
                return ReconciliationDecision(HALT, False, reason, len(broker_positions))

    if local is None:
        if not broker_positions:
            return ReconciliationDecision(ALLOW, True, "local and broker are both flat", 0)
        return ReconciliationDecision(HALT, False, "broker has position but local state is flat", len(broker_positions))

    if broker_contract is not None and local.symbol != broker_contract.symbol:
        return ReconciliationDecision(HALT, False, "local position symbol differs from broker contract", len(broker_positions))

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

    if local.average_entry_price is not None and broker.average_entry_price is None:
        return ReconciliationDecision(HALT, False, "broker average entry price is missing", 1)
    if local.average_entry_price is not None and broker.average_entry_price is not None:
        if abs(broker.average_entry_price - local.average_entry_price) > price_tolerance:
            return ReconciliationDecision(HALT, False, "broker average entry price differs from local state", 1)

    return ReconciliationDecision(ALLOW, True, "local and broker position state reconciled", 1)


def new_entry_allowed(
    local: LocalPositionState | None,
    broker_positions: list[PositionSnapshot],
    *,
    quantity_tolerance: float = 1e-12,
    price_tolerance: float = 1e-12,
    broker_contract: SymbolContract | None = None,
) -> ReconciliationDecision:
    """Only permit a new entry when both sides agree that the account is flat."""
    decision = reconcile_position(
        local,
        broker_positions,
        quantity_tolerance=quantity_tolerance,
        price_tolerance=price_tolerance,
        broker_contract=broker_contract,
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
