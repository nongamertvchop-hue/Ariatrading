"""Conformance helpers for the non-broker paper execution boundary.

The conformance layer verifies that an order lifecycle remains safe across
submission, ambiguous responses, reconnect, broker reconciliation, and
idempotent retry. It has no network or broker side effects.
"""

from __future__ import annotations

from dataclasses import dataclass

from adapters.paper_broker import (
    FILLED,
    PARTIALLY_FILLED,
    REJECTED,
    PaperBrokerSimulator,
    PaperOrderRequest,
    PaperOrderSnapshot,
)
from .order_state import OrderState, OrderStateMachine


@dataclass(frozen=True)
class RecoveryResult:
    """Result of reconciling one locally ambiguous order."""

    state: OrderState
    filled_quantity: float
    broker_status: str
    retry_submitted: bool


def submit_with_recovery(
    broker: PaperBrokerSimulator,
    orders: OrderStateMachine,
    request: PaperOrderRequest,
    *,
    idempotency_key: str,
) -> RecoveryResult:
    """Drive one paper order through a fail-closed ambiguous-response path.

    A timeout after broker acceptance is represented locally as UNKNOWN. The
    function reconnects/reconciles the broker snapshot before allowing the
    idempotent request to be observed again. It never blindly submits a second
    logical order.
    """
    created = orders.create(
        client_order_id=request.client_order_id,
        idempotency_key=idempotency_key,
        direction=request.direction,
        quantity=request.quantity,
    )
    if created.accepted:
        orders.transition(request.client_order_id, OrderState.SUBMITTING)

    try:
        snapshot = broker.submit(request)
    except TimeoutError:
        orders.transition(request.client_order_id, OrderState.UNKNOWN)
        if not broker.connected:
            broker.reconnect()
        snapshot = broker.get_order(request.client_order_id)
        if snapshot is None:
            return RecoveryResult(OrderState.UNKNOWN, 0.0, "MISSING", False)
        recovered = _apply_snapshot(orders, snapshot)
        return RecoveryResult(recovered.state, recovered.filled_quantity, recovered.broker_status, False)

    recovered = _apply_snapshot(orders, snapshot)
    return RecoveryResult(recovered.state, recovered.filled_quantity, recovered.broker_status, False)


def _apply_snapshot(
    orders: OrderStateMachine,
    snapshot: PaperOrderSnapshot,
) -> RecoveryResult:
    if snapshot.status == FILLED:
        transition = orders.transition(
            snapshot.client_order_id,
            OrderState.FILLED,
            filled_quantity=snapshot.filled_quantity,
        )
    elif snapshot.status == PARTIALLY_FILLED:
        transition = orders.transition(
            snapshot.client_order_id,
            OrderState.PARTIALLY_FILLED,
            filled_quantity=snapshot.filled_quantity,
        )
    elif snapshot.status == REJECTED:
        transition = orders.transition(snapshot.client_order_id, OrderState.REJECTED)
    else:
        raise ValueError(f"unsupported broker snapshot status: {snapshot.status}")

    if not transition.accepted:
        raise RuntimeError(f"order-state reconciliation failed: {transition.reason}")
    return RecoveryResult(
        transition.record.state,
        transition.record.filled_quantity,
        snapshot.status,
        False,
    )


__all__ = ["RecoveryResult", "submit_with_recovery"]
