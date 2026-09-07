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
    """Drive one paper order through a fail-closed submission boundary.

    A timeout after broker acceptance is represented locally as UNKNOWN. The
    broker snapshot is reconciled before the result is finalized. A repeated
    call with the same idempotency key only observes the existing broker order;
    it never creates another logical submission.
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
    except ConnectionError:
        if created.accepted:
            orders.transition(request.client_order_id, OrderState.UNKNOWN)
        raise
    except TimeoutError:
        orders.transition(request.client_order_id, OrderState.UNKNOWN)
        snapshot = broker.get_order(request.client_order_id)
        if snapshot is None:
            return RecoveryResult(OrderState.UNKNOWN, 0.0, "MISSING", False)
        return _reconcile_snapshot(orders, snapshot)

    return _reconcile_snapshot(orders, snapshot)


def _reconcile_snapshot(
    orders: OrderStateMachine,
    snapshot: PaperOrderSnapshot,
) -> RecoveryResult:
    current = orders.get(snapshot.client_order_id)

    if snapshot.status == FILLED:
        target = OrderState.FILLED
    elif snapshot.status == PARTIALLY_FILLED:
        target = OrderState.PARTIALLY_FILLED
    elif snapshot.status == REJECTED:
        target = OrderState.REJECTED
    else:
        raise ValueError(f"unsupported broker snapshot status: {snapshot.status}")

    if current.state == target and current.filled_quantity == snapshot.filled_quantity:
        return RecoveryResult(target, current.filled_quantity, snapshot.status, False)

    transition = orders.transition(
        snapshot.client_order_id,
        target,
        filled_quantity=snapshot.filled_quantity,
    )
    if not transition.accepted:
        raise RuntimeError(f"order-state reconciliation failed: {transition.reason}")
    return RecoveryResult(
        transition.record.state,
        transition.record.filled_quantity,
        snapshot.status,
        False,
    )


__all__ = ["RecoveryResult", "submit_with_recovery"]
