from datetime import datetime, timezone

import pytest

from adapters.paper_broker import FILLED, LONG, PARTIALLY_FILLED, PaperBrokerSimulator, PaperOrderRequest
from strategy.order_state import OrderState, OrderStateMachine
from strategy.paper_execution_conformance import submit_with_recovery


NOW = datetime(2026, 9, 7, 3, 30, tzinfo=timezone.utc)


def make_request(client_order_id: str = "ord-1") -> PaperOrderRequest:
    return PaperOrderRequest(
        client_order_id=client_order_id,
        symbol="EURUSD",
        direction=LONG,
        quantity=1.0,
        price=1.1000,
        submitted_at=NOW,
    )


def test_timeout_after_accept_recovers_without_duplicate_submission():
    broker = PaperBrokerSimulator()
    broker.configure_next_timeout_after_accept()
    orders = OrderStateMachine()

    result = submit_with_recovery(broker, orders, make_request(), idempotency_key="idem-1")

    assert result.state is OrderState.FILLED
    assert result.filled_quantity == 1.0
    assert result.broker_status == FILLED
    assert len(broker.list_orders()) == 1
    assert len(broker.positions()) == 1


def test_repeated_recovery_call_is_idempotent():
    broker = PaperBrokerSimulator()
    broker.configure_next_timeout_after_accept()
    orders = OrderStateMachine()
    request = make_request()

    first = submit_with_recovery(broker, orders, request, idempotency_key="idem-1")
    second = submit_with_recovery(broker, orders, request, idempotency_key="idem-1")

    assert first == second
    assert len(broker.list_orders()) == 1
    assert len(broker.positions()) == 1


def test_partial_fill_is_preserved_by_conformance_boundary():
    broker = PaperBrokerSimulator(fill_fraction=0.5)
    orders = OrderStateMachine()

    result = submit_with_recovery(broker, orders, make_request(), idempotency_key="idem-1")

    assert result.state is OrderState.PARTIALLY_FILLED
    assert result.filled_quantity == pytest.approx(0.5)
    assert result.broker_status == PARTIALLY_FILLED
    assert orders.get("ord-1").filled_quantity == pytest.approx(0.5)


def test_disconnect_fails_closed_and_marks_local_order_unknown():
    broker = PaperBrokerSimulator()
    broker.disconnect()
    orders = OrderStateMachine()

    with pytest.raises(ConnectionError):
        submit_with_recovery(broker, orders, make_request(), idempotency_key="idem-1")

    assert broker.list_orders() == ()
    assert orders.get("ord-1").state is OrderState.UNKNOWN
