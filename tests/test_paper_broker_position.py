from datetime import datetime, timezone

from adapters.paper_broker import LONG, SHORT, PaperBrokerSimulator, PaperOrderRequest


T1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
T2 = datetime(2026, 1, 2, tzinfo=timezone.utc)


def request(order_id: str, direction: str, quantity: float, price: float, when: datetime) -> PaperOrderRequest:
    return PaperOrderRequest(order_id, "EURUSD", direction, quantity, price, when)


def test_opposite_fill_reduces_position_without_repricing_remainder() -> None:
    broker = PaperBrokerSimulator()
    broker.submit(request("open", LONG, 2.0, 1.1000, T1))

    broker.submit(request("reduce", SHORT, 0.5, 1.0900, T2))

    position = broker.positions()[0]
    assert position.net_quantity == 1.5
    assert position.average_price == 1.1000


def test_opposite_fill_that_reverses_starts_new_average_price() -> None:
    broker = PaperBrokerSimulator()
    broker.submit(request("open", LONG, 1.0, 1.1000, T1))

    broker.submit(request("reverse", SHORT, 2.0, 1.0900, T2))

    position = broker.positions()[0]
    assert position.net_quantity == -1.0
    assert position.average_price == 1.0900
