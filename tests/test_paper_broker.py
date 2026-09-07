from datetime import datetime, timezone

import pytest

from adapters.paper_broker import (
    FILLED,
    PARTIALLY_FILLED,
    REJECTED,
    LONG,
    PaperBrokerSimulator,
    PaperOrderRequest,
)


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_request(order_id: str = "order-1", quantity: float = 1.0) -> PaperOrderRequest:
    return PaperOrderRequest(
        client_order_id=order_id,
        symbol="EURUSD",
        direction=LONG,
        quantity=quantity,
        price=1.1000,
        submitted_at=NOW,
    )


def test_full_fill_updates_position() -> None:
    broker = PaperBrokerSimulator()

    snapshot = broker.submit(make_request(quantity=2.0))

    assert snapshot.status == FILLED
    assert snapshot.filled_quantity == 2.0
    assert snapshot.average_fill_price == 1.1
    assert broker.positions()[0].net_quantity == 2.0


def test_partial_fill_is_deterministic() -> None:
    broker = PaperBrokerSimulator(fill_fraction=0.25)

    snapshot = broker.submit(make_request(quantity=4.0))

    assert snapshot.status == PARTIALLY_FILLED
    assert snapshot.filled_quantity == 1.0
    assert snapshot.remaining_quantity == 3.0


def test_repeated_client_order_id_is_idempotent() -> None:
    broker = PaperBrokerSimulator()
    request = make_request()

    first = broker.submit(request)
    second = broker.submit(request)

    assert second == first
    assert len(broker.list_orders()) == 1
    assert broker.positions()[0].net_quantity == 1.0


def test_rejection_does_not_change_position() -> None:
    broker = PaperBrokerSimulator(reject_next=True)

    snapshot = broker.submit(make_request())

    assert snapshot.status == REJECTED
    assert snapshot.filled_quantity == 0.0
    assert broker.positions() == ()


def test_timeout_after_accept_requires_reconciliation() -> None:
    broker = PaperBrokerSimulator()
    broker.configure_next_timeout_after_accept()

    with pytest.raises(TimeoutError):
        broker.submit(make_request())

    resolved = broker.get_order("order-1")
    assert resolved is not None
    assert resolved.status == FILLED
    assert resolved.filled_quantity == 1.0
    assert broker.positions()[0].net_quantity == 1.0


def test_disconnect_blocks_submit_and_recovery_restores_access() -> None:
    broker = PaperBrokerSimulator()
    broker.disconnect()

    with pytest.raises(ConnectionError):
        broker.submit(make_request())

    broker.reconnect()
    snapshot = broker.submit(make_request())
    assert snapshot.status == FILLED


def test_invalid_request_fails_closed() -> None:
    broker = PaperBrokerSimulator()
    request = make_request(quantity=0.0)

    with pytest.raises(ValueError):
        broker.submit(request)
