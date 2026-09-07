import json

import pytest

from strategy.order_persistence import OrderPersistenceError, load_order_state, save_order_state
from strategy.order_state import OrderState, OrderStateMachine


def test_save_and_load_round_trip(tmp_path):
    machine = OrderStateMachine()
    created = machine.create(
        client_order_id="c-1",
        idempotency_key="idem-1",
        direction="LONG",
        quantity=2.5,
    )
    assert created.accepted
    machine.transition("c-1", OrderState.SUBMITTING)
    machine.transition("c-1", OrderState.ACKNOWLEDGED, broker_order_id="b-9")
    machine.transition("c-1", OrderState.PARTIALLY_FILLED, filled_quantity=1.0)

    path = tmp_path / "orders.json"
    save_order_state(machine, path)
    restored = load_order_state(path)
    record = restored.get("c-1")

    assert record.state == OrderState.PARTIALLY_FILLED
    assert record.broker_order_id == "b-9"
    assert record.filled_quantity == 1.0
    assert record.quantity == 2.5


def test_save_replaces_previous_snapshot_atomically(tmp_path):
    machine = OrderStateMachine()
    machine.create(client_order_id="c-1", idempotency_key="i-1", direction="SHORT", quantity=1.0)
    path = tmp_path / "orders.json"
    save_order_state(machine, path)
    first = path.read_text(encoding="utf-8")

    machine.create(client_order_id="c-2", idempotency_key="i-2", direction="LONG", quantity=2.0)
    save_order_state(machine, path)
    second = path.read_text(encoding="utf-8")

    assert first != second
    assert {item["client_order_id"] for item in json.loads(second)["orders"]} == {"c-1", "c-2"}


def test_malformed_snapshot_fails_closed(tmp_path):
    path = tmp_path / "orders.json"
    path.write_text("not-json", encoding="utf-8")
    with pytest.raises(OrderPersistenceError):
        load_order_state(path)


def test_invalid_state_snapshot_is_rejected(tmp_path):
    path = tmp_path / "orders.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "orders": [
                    {
                        "client_order_id": "c-1",
                        "idempotency_key": "i-1",
                        "direction": "LONG",
                        "quantity": 1.0,
                        "state": "FILLED",
                        "filled_quantity": 0.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(OrderPersistenceError):
        load_order_state(path)


def test_missing_snapshot_fails_closed(tmp_path):
    with pytest.raises(OrderPersistenceError):
        load_order_state(tmp_path / "missing.json")
