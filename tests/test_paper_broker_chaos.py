from datetime import datetime, timedelta, timezone

from strategy.feed_integrity import validate_feed_batch
from strategy.paper_broker import ChaosScenario, PaperBroker
from strategy.position_reconciliation import LocalPositionState, reconcile_position


class Bar:
    def __init__(self, timestamp, open_, high, low, close):
        self.time = timestamp
        self.open = open_
        self.high = high
        self.low = low
        self.close = close


def _bars(count=6):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [Bar(start + timedelta(minutes=i), 1.1000, 1.1010, 1.0990, 1.1005) for i in range(count)]


def test_three_consecutive_rejections_are_reproducible():
    broker = PaperBroker()
    for attempt in range(1, 4):
        result = broker.submit_market_order(
            client_order_id="chaos-1",
            direction="LONG",
            quantity=0.10,
            scenario=ChaosScenario.REJECT_MARKET_ORDER_THREE_TIMES,
        )
        assert not result.accepted
        assert result.status == "REJECTED"
        assert result.attempts == attempt

    result = broker.submit_market_order(
        client_order_id="chaos-1",
        direction="LONG",
        quantity=0.10,
        scenario=ChaosScenario.REJECT_MARKET_ORDER_THREE_TIMES,
    )
    assert result.accepted
    assert result.status == "FILLED"
    assert result.attempts == 4


def test_rounded_volume_is_reconcilable_with_realistic_tolerance():
    broker = PaperBroker()
    result = broker.submit_market_order(
        client_order_id="chaos-2",
        direction="LONG",
        quantity=0.10,
        scenario=ChaosScenario.NORMAL,
    )
    broker_position = broker.positions(ChaosScenario.ROUNDED_VOLUME)
    local = LocalPositionState("EURUSD", "LONG", result.filled_quantity, result.broker_order_id)

    decision = reconcile_position(local, broker_position, quantity_tolerance=1e-5)
    assert decision.safe


def test_out_of_order_candles_are_rejected_by_feed_integrity():
    broker = PaperBroker()
    distorted = broker.distort_candles(_bars(), ChaosScenario.OUT_OF_ORDER_CANDLES)
    report = validate_feed_batch(distorted, "1m")
    assert not report.ok
    assert report.out_of_order_count == 1


def test_temporary_missing_candle_is_detected_in_strict_feed_mode():
    broker = PaperBroker()
    distorted = broker.distort_candles(_bars(), ChaosScenario.TEMPORARY_MISSING_CANDLES)
    report = validate_feed_batch(distorted, "1m", require_contiguous=True)
    assert not report.ok
    assert report.missing_count == 1
