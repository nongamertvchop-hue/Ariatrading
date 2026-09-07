from datetime import datetime, timedelta, timezone

import pytest

from adapters.paper_broker import (
    FILLED,
    PARTIALLY_FILLED,
    REJECTED,
    LONG,
    ChaosScenario,
    PaperBrokerSimulator,
    PaperOrderRequest,
)
from strategy.feed_integrity import validate_feed_batch


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


class Bar:
    def __init__(self, timestamp):
        self.time = timestamp
        self.open = 1.1000
        self.high = 1.1010
        self.low = 1.0990
        self.close = 1.1005


def make_bars(count: int = 6) -> list[Bar]:
    return [Bar(NOW + timedelta(minutes=i)) for i in range(count)]


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


def test_three_rejections_are_exactly_three_then_fill() -> None:
    broker = PaperBrokerSimulator()

    for _ in range(3):
        snapshot = broker.submit(make_request(order_id="chaos-reject"), scenario=ChaosScenario.REJECT_THREE_TIMES)
        assert snapshot.status == REJECTED
        assert broker.positions() == ()

    snapshot = broker.submit(make_request(order_id="chaos-reject"), scenario=ChaosScenario.REJECT_THREE_TIMES)
    assert snapshot.status == FILLED
    assert broker.positions()[0].net_quantity == 1.0


def test_rounded_volume_noise_is_deterministic() -> None:
    broker = PaperBrokerSimulator()
    broker.submit(make_request(quantity=0.10))
    broker.configure_volume_noise(1e-5)

    noisy = broker.positions(scenario=ChaosScenario.ROUNDED_VOLUME)
    normal = broker.positions()

    assert noisy[0].net_quantity == pytest.approx(normal[0].net_quantity + 1e-5)
    assert noisy[0].average_price == normal[0].average_price


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


def test_out_of_order_candles_are_rejected_by_feed_integrity() -> None:
    broker = PaperBrokerSimulator()
    candles = make_bars()
    distorted = broker.distort_candles(candles, ChaosScenario.OUT_OF_ORDER_CANDLES)

    report = validate_feed_batch(distorted, "1m")

    assert not report.ok
    assert report.out_of_order_count == 1


def test_missing_candle_is_detected_when_contiguous_stream_is_required() -> None:
    broker = PaperBrokerSimulator()
    candles = make_bars()
    distorted = broker.distort_candles(candles, ChaosScenario.TEMPORARY_MISSING_CANDLES)

    report = validate_feed_batch(distorted, "1m", require_contiguous=True)

    assert not report.ok
    assert report.missing_count == 1


def test_invalid_request_fails_closed() -> None:
    broker = PaperBrokerSimulator()
    request = make_request(quantity=0.0)

    with pytest.raises(ValueError):
        broker.submit(request)
