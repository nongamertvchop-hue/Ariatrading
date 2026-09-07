import pytest

from strategy.order_state import OrderState, OrderStateMachine


def test_create_is_idempotent_for_same_request():
    machine = OrderStateMachine()
    first = machine.create(
        client_order_id="client-1",
        idempotency_key="idem-1",
        direction="LONG",
        quantity=10.0,
    )
    second = machine.create(
        client_order_id="client-1",
        idempotency_key="idem-1",
        direction="LONG",
        quantity=10.0,
    )
    assert first.accepted
    assert not second.accepted
    assert second.record == first.record


def test_reusing_idempotency_key_for_different_request_fails():
    machine = OrderStateMachine()
    machine.create(client_order_id="client-1", idempotency_key="idem-1", direction="LONG", quantity=10.0)
    with pytest.raises(ValueError):
        machine.create(client_order_id="client-2", idempotency_key="idem-1", direction="SHORT", quantity=5.0)


def test_lifecycle_accepts_normal_fill_path():
    machine = OrderStateMachine()
    machine.create(client_order_id="client-1", idempotency_key="idem-1", direction="LONG", quantity=10.0)
    assert machine.transition("client-1", OrderState.SUBMITTING).accepted
    assert machine.transition("client-1", OrderState.ACKNOWLEDGED, broker_order_id="broker-1").accepted
    assert machine.transition("client-1", OrderState.PARTIALLY_FILLED, filled_quantity=4.0).accepted
    filled = machine.transition("client-1", OrderState.FILLED, filled_quantity=10.0)
    assert filled.accepted
    assert filled.record.filled_quantity == 10.0
    assert machine.transition("client-1", OrderState.CLOSED).accepted


def test_invalid_transition_is_rejected_without_state_change():
    machine = OrderStateMachine()
    machine.create(client_order_id="client-1", idempotency_key="idem-1", direction="LONG", quantity=10.0)
    result = machine.transition("client-1", OrderState.FILLED)
    assert not result.accepted
    assert machine.get("client-1").state == OrderState.CREATED


def test_unknown_state_is_recoverable_by_reconciliation():
    machine = OrderStateMachine()
    machine.create(client_order_id="client-1", idempotency_key="idem-1", direction="SHORT", quantity=3.0)
    machine.transition("client-1", OrderState.SUBMITTING)
    unknown = machine.transition("client-1", OrderState.UNKNOWN)
    assert unknown.accepted
    recovered = machine.transition("client-1", OrderState.ACKNOWLEDGED, broker_order_id="broker-9")
    assert recovered.accepted


def test_terminal_state_cannot_transition_again():
    machine = OrderStateMachine()
    machine.create(client_order_id="client-1", idempotency_key="idem-1", direction="LONG", quantity=1.0)
    machine.transition("client-1", OrderState.CANCELLED)  # type: ignore[arg-type]
    result = machine.transition("client-1", OrderState.CREATED)
    assert not result.accepted
