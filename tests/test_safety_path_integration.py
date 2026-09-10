from datetime import datetime, timedelta, timezone

import pytest

from adapters.paper_broker import LONG, PaperBrokerSimulator, PaperOrderRequest
from strategy.broker_contract import SymbolContract
from strategy.execution_audit import AuditJournal
from strategy.execution_recovery import ExecutionRecoveryDecision, verify_execution_recovery
from strategy.order_state import OrderState, OrderStateMachine
from strategy.paper_execution_conformance import submit_with_recovery
from strategy.position_reconciliation import (
    HALT,
    LocalPositionState,
    PositionSnapshot,
    new_entry_allowed,
    reconcile_position,
)
from strategy.realtime_replay import replay_realtime_monitor


NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
CONTRACT = SymbolContract(
    symbol="EURUSD",
    digits=5,
    point=0.00001,
    volume_min=0.1,
    volume_max=100.0,
    volume_step=0.1,
)


def make_request(client_order_id: str = "ord-integration") -> PaperOrderRequest:
    return PaperOrderRequest(
        client_order_id=client_order_id,
        symbol="EURUSD",
        direction=LONG,
        quantity=1.0,
        price=1.10000,
        submitted_at=NOW,
    )


def make_candles(n: int = 24) -> list[dict]:
    price = 1.10000
    candles: list[dict] = []
    for index in range(n):
        move = 0.0002 if index % 2 == 0 else -0.0001
        candles.append(
            {
                "time": NOW + timedelta(minutes=index),
                "open": price,
                "high": price + 0.0005,
                "low": price - 0.0005,
                "close": price + move,
            }
        )
        price += move
    return candles


def test_execution_recovery_and_audit_converge_after_timeout(tmp_path):
    broker = PaperBrokerSimulator()
    broker.configure_next_timeout_after_accept()
    orders = OrderStateMachine()

    result = submit_with_recovery(
        broker,
        orders,
        make_request(),
        idempotency_key="idem-integration",
    )

    assert result.state is OrderState.FILLED
    assert len(broker.list_orders()) == 1

    recovered = orders.get("ord-integration")
    journal = AuditJournal(tmp_path / "execution.jsonl")
    journal.append(
        event_id="evt-1",
        event_type="ORDER_RECOVERED",
        client_order_id=recovered.client_order_id,
        state=recovered.state.value,
        broker_order_id=recovered.broker_order_id,
        filled_quantity=recovered.filled_quantity,
        reason="timeout recovery",
    )

    report = verify_execution_recovery(orders, journal)
    assert report.decision is ExecutionRecoveryDecision.ALLOW
    assert report.issues == ()


def test_execution_recovery_halts_on_audit_tamper(tmp_path):
    broker = PaperBrokerSimulator()
    orders = OrderStateMachine()
    submit_with_recovery(
        broker,
        orders,
        make_request("ord-tamper"),
        idempotency_key="idem-tamper",
    )
    record = orders.get("ord-tamper")

    path = tmp_path / "execution.jsonl"
    journal = AuditJournal(path)
    journal.append(
        event_id="evt-tamper",
        event_type="ORDER_FILLED",
        client_order_id=record.client_order_id,
        state=record.state.value,
        broker_order_id=record.broker_order_id,
        filled_quantity=record.filled_quantity,
    )
    raw = path.read_text(encoding="utf-8")
    path.write_text(raw.replace('"filled_quantity":1.0', '"filled_quantity":0.5'), encoding="utf-8")

    report = verify_execution_recovery(orders, journal)
    assert report.decision is ExecutionRecoveryDecision.HALT
    assert any("audit verification failed" in issue for issue in report.issues)


def test_reconciliation_allows_exact_position_and_blocks_divergence():
    local = LocalPositionState(
        symbol="EURUSD",
        direction="LONG",
        quantity=1.0,
        position_id="pos-1",
        average_entry_price=1.10000,
    )
    broker = PositionSnapshot(
        symbol="EURUSD",
        direction="LONG",
        quantity=1.0,
        position_id="pos-1",
        average_entry_price=1.10000,
    )

    allowed = reconcile_position(local, [broker], broker_contract=CONTRACT)
    assert allowed.safe is True

    mismatched = PositionSnapshot(
        symbol="EURUSD",
        direction="LONG",
        quantity=1.1,
        position_id="pos-1",
        average_entry_price=1.10000,
    )
    halted = reconcile_position(local, [mismatched], broker_contract=CONTRACT)
    assert halted.action == HALT
    assert halted.safe is False


def test_new_entry_requires_both_local_and_broker_flat():
    assert new_entry_allowed(None, [], broker_contract=CONTRACT).safe is True

    local = LocalPositionState(
        symbol="EURUSD",
        direction="LONG",
        quantity=1.0,
        position_id="pos-2",
        average_entry_price=1.10000,
    )
    blocked = new_entry_allowed(local, [], broker_contract=CONTRACT)
    assert blocked.action == HALT
    assert blocked.safe is False
    assert "existing position" in blocked.reason


def test_reconciliation_halts_duplicate_broker_positions():
    first = PositionSnapshot("EURUSD", "LONG", 1.0, "dup", 1.10000)
    second = PositionSnapshot("EURUSD", "LONG", 0.5, "dup", 1.10100)
    decision = reconcile_position(None, [first, second], broker_contract=CONTRACT)
    assert decision.action == HALT
    assert "duplicate broker position id" in decision.reason


def test_replay_is_causal_and_repeatable():
    candles = make_candles()
    first = replay_realtime_monitor(candles, "EURUSD", "1m", lookback=20)
    second = replay_realtime_monitor(candles, "EURUSD", "1m", lookback=20)

    assert first == second
    assert first.count == second.count
    assert first.event_ids == second.event_ids
    assert len(set(first.event_ids)) == first.count


def test_replay_rejects_duplicated_timestamps():
    candles = make_candles(12)
    candles[5]["time"] = candles[4]["time"]
    with pytest.raises(ValueError):
        replay_realtime_monitor(candles, "EURUSD", "1m", lookback=10)
