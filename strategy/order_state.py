"""Deterministic order lifecycle state machine with idempotency safeguards.

This module models execution state only. It does not place broker orders and it
never creates LONG/SHORT signals. Repeated client requests with the same
idempotency key cannot create a second logical order, while ambiguous failures
remain in a non-terminal state until reconciled externally.
"""

from dataclasses import dataclass
from enum import Enum


class OrderState(str, Enum):
    CREATED = "CREATED"
    SUBMITTING = "SUBMITTING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"
    CLOSED = "CLOSED"


_TERMINAL = {OrderState.CANCELLED, OrderState.REJECTED, OrderState.CLOSED}
_ALLOWED = {
    OrderState.CREATED: {OrderState.SUBMITTING, OrderState.CANCELLED},
    OrderState.SUBMITTING: {
        OrderState.ACKNOWLEDGED,
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.REJECTED,
        OrderState.UNKNOWN,
    },
    OrderState.ACKNOWLEDGED: {
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.CANCEL_PENDING,
        OrderState.UNKNOWN,
    },
    OrderState.PARTIALLY_FILLED: {
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.CANCEL_PENDING,
        OrderState.UNKNOWN,
    },
    OrderState.CANCEL_PENDING: {
        OrderState.CANCELLED,
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.UNKNOWN,
    },
    OrderState.UNKNOWN: {
        OrderState.ACKNOWLEDGED,
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.CANCELLED,
        OrderState.REJECTED,
        OrderState.CLOSED,
    },
    OrderState.FILLED: {OrderState.CLOSED},
    OrderState.CANCELLED: set(),
    OrderState.REJECTED: set(),
    OrderState.CLOSED: set(),
}


@dataclass(frozen=True)
class OrderRecord:
    client_order_id: str
    idempotency_key: str
    direction: str
    quantity: float
    state: OrderState = OrderState.CREATED
    broker_order_id: str | None = None
    filled_quantity: float = 0.0


@dataclass(frozen=True)
class OrderTransition:
    accepted: bool
    record: OrderRecord
    reason: str


class OrderStateMachine:
    """In-memory order lifecycle registry for deterministic execution logic."""

    def __init__(self) -> None:
        self._orders_by_client_id: dict[str, OrderRecord] = {}
        self._client_id_by_idempotency: dict[str, str] = {}

    def create(
        self,
        *,
        client_order_id: str,
        idempotency_key: str,
        direction: str,
        quantity: float,
    ) -> OrderTransition:
        if not client_order_id:
            raise ValueError("client_order_id must not be empty")
        if not idempotency_key:
            raise ValueError("idempotency_key must not be empty")
        if direction not in {"LONG", "SHORT"}:
            raise ValueError("direction must be LONG or SHORT")
        if quantity <= 0:
            raise ValueError("quantity must be > 0")

        existing_client_id = self._client_id_by_idempotency.get(idempotency_key)
        if existing_client_id is not None:
            existing = self._orders_by_client_id[existing_client_id]
            if (
                existing.client_order_id == client_order_id
                and existing.direction == direction
                and existing.quantity == quantity
            ):
                return OrderTransition(False, existing, "duplicate idempotency key; returning existing order")
            raise ValueError("idempotency key already belongs to a different order request")

        if client_order_id in self._orders_by_client_id:
            raise ValueError("client_order_id already exists")

        record = OrderRecord(client_order_id, idempotency_key, direction, float(quantity))
        self._orders_by_client_id[client_order_id] = record
        self._client_id_by_idempotency[idempotency_key] = client_order_id
        return OrderTransition(True, record, "order created")

    def transition(
        self,
        client_order_id: str,
        new_state: OrderState,
        *,
        broker_order_id: str | None = None,
        filled_quantity: float | None = None,
    ) -> OrderTransition:
        current = self.get(client_order_id)
        if current.state in _TERMINAL:
            return OrderTransition(False, current, "terminal order state cannot transition")
        if new_state not in _ALLOWED[current.state]:
            return OrderTransition(False, current, f"invalid transition {current.state.value} -> {new_state.value}")

        quantity = current.filled_quantity if filled_quantity is None else float(filled_quantity)
        if quantity < 0 or quantity > current.quantity:
            raise ValueError("filled_quantity must be between 0 and order quantity")
        if new_state == OrderState.FILLED and quantity != current.quantity:
            quantity = current.quantity

        broker_id = broker_order_id if broker_order_id is not None else current.broker_order_id
        record = OrderRecord(
            current.client_order_id,
            current.idempotency_key,
            current.direction,
            current.quantity,
            new_state,
            broker_id,
            quantity,
        )
        self._orders_by_client_id[client_order_id] = record
        return OrderTransition(True, record, "state transition accepted")

    def restore(self, record: OrderRecord) -> OrderRecord:
        """Restore a previously persisted record after validating its invariants.

        Recovery must not replay the lifecycle from CREATED because a snapshot
        intentionally contains only the latest state, not the historical events.
        """
        if not isinstance(record, OrderRecord):
            raise TypeError("record must be an OrderRecord")
        if not record.client_order_id:
            raise ValueError("client_order_id must not be empty")
        if not record.idempotency_key:
            raise ValueError("idempotency_key must not be empty")
        if record.direction not in {"LONG", "SHORT"}:
            raise ValueError("direction must be LONG or SHORT")
        if record.quantity <= 0:
            raise ValueError("quantity must be > 0")
        if not isinstance(record.state, OrderState):
            raise ValueError("state must be an OrderState")
        if record.filled_quantity < 0 or record.filled_quantity > record.quantity:
            raise ValueError("filled_quantity must be between 0 and order quantity")
        if record.state in {OrderState.CREATED, OrderState.SUBMITTING} and record.filled_quantity != 0:
            raise ValueError("CREATED/SUBMITTING orders cannot have filled quantity")
        if record.state in {OrderState.FILLED, OrderState.CLOSED} and record.filled_quantity != record.quantity:
            raise ValueError("FILLED/CLOSED orders must have full filled quantity")

        existing_client = self._orders_by_client_id.get(record.client_order_id)
        if existing_client is not None and existing_client != record:
            raise ValueError("client_order_id already exists with different order data")
        existing_idempotency = self._client_id_by_idempotency.get(record.idempotency_key)
        if existing_idempotency is not None and existing_idempotency != record.client_order_id:
            raise ValueError("idempotency key already belongs to a different order")

        self._orders_by_client_id[record.client_order_id] = record
        self._client_id_by_idempotency[record.idempotency_key] = record.client_order_id
        return record

    def get(self, client_order_id: str) -> OrderRecord:
        try:
            return self._orders_by_client_id[client_order_id]
        except KeyError as exc:
            raise KeyError(f"unknown client_order_id: {client_order_id}") from exc

    def all_orders(self) -> tuple[OrderRecord, ...]:
        return tuple(self._orders_by_client_id.values())
