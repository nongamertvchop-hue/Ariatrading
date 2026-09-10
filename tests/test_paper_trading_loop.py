from datetime import datetime, timezone
from pathlib import Path

import pytest

from adapters.paper_broker import PaperBrokerSimulator, LONG
from strategy.broker_contract import SymbolContract
from strategy.engine import EngineSignal
from strategy.execution_recovery import ExecutionRecoveryDecision
from strategy.paper_trading_loop import PaperTradingLoop
from strategy.portfolio_risk import PortfolioRiskDecision
from strategy.realtime_guard import DataQuality
from strategy.risk_engine import RiskDecision


NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


CONTRACT = SymbolContract(
    symbol="EURUSD",
    digits=4,
    point=0.0001,
    volume_min=0.1,
    volume_max=100.0,
    volume_step=0.1,
)

SIGNAL = EngineSignal(
    action=LONG,
    reason="support reclaim confirmed",
    timeframe="5m",
    entry_reference=1.1000,
    stop_reference=1.0950,
    protection="SAFE",
)

DATA_OK = DataQuality(True, "ok", NOW, 1.0)
PORTFOLIO_OK = PortfolioRiskDecision("ALLOW", True, "portfolio risk limits passed", 0.0, 0.0, 0)
RISK_OK = RiskDecision(True, "risk checks passed", 1.0, 0.005, 0.005)


def make_loop(tmp_path: Path, broker: PaperBrokerSimulator | None = None) -> PaperTradingLoop:
    return PaperTradingLoop(
        broker=broker or PaperBrokerSimulator(),
        journal_path=tmp_path / "execution.jsonl",
        symbol="EURUSD",
        contract=CONTRACT,
    )


def run_open(loop: PaperTradingLoop, order_id: str = "ord-1"):
    return loop.run_entry(
        signal=SIGNAL,
        data_quality=DATA_OK,
        portfolio_risk=PORTFOLIO_OK,
        risk=RISK_OK,
        idempotency_key=f"idem-{order_id}",
        client_order_id=order_id,
        submitted_at=NOW,
    )


def test_end_to_end_open_reconcile_and_close(tmp_path: Path):
    loop = make_loop(tmp_path)

    opened = run_open(loop)
    assert opened.action == "OPEN"
    assert opened.allowed
    assert opened.reconciled
    assert opened.position is not None
    assert opened.recovery is not None
    assert opened.recovery.decision is ExecutionRecoveryDecision.ALLOW

    closed = loop.close_position(
        price=1.1010,
        client_order_id="close-1",
        idempotency_key="close-idem-1",
        submitted_at=NOW,
    )
    assert closed.action == "CLOSED"
    assert closed.allowed
    assert closed.reconciled
    assert loop.position is None
    assert loop.broker.positions() == ()


def test_timeout_after_accept_is_recovered_to_open_without_duplicate(tmp_path: Path):
    broker = PaperBrokerSimulator(timeout_after_accept_next=True)
    loop = make_loop(tmp_path, broker)

    opened = run_open(loop)

    assert opened.action == "OPEN"
    assert opened.order_state is not None
    assert opened.order_state.value == "FILLED"
    assert len(broker.list_orders()) == 1
    assert len(broker.positions()) == 1
    assert opened.recovery is not None
    assert opened.recovery.decision is ExecutionRecoveryDecision.ALLOW


def test_disconnect_before_submit_fails_closed_and_leaves_unknown(tmp_path: Path):
    broker = PaperBrokerSimulator()
    broker.disconnect()
    loop = make_loop(tmp_path, broker)

    result = run_open(loop)

    assert result.action == "HALT"
    assert not result.allowed
    assert result.order_state is not None
    assert result.order_state.value == "UNKNOWN"
    assert broker.list_orders() == ()
    assert result.recovery is not None
    assert result.recovery.decision is ExecutionRecoveryDecision.ALLOW


def test_broker_rejection_is_never_promoted_to_position(tmp_path: Path):
    broker = PaperBrokerSimulator(reject_next=True)
    loop = make_loop(tmp_path, broker)

    result = run_open(loop)

    assert result.action == "REJECTED"
    assert not result.allowed
    assert result.position is None
    assert broker.positions() == ()


def test_position_disappearance_is_detected_on_next_cycle(tmp_path: Path):
    broker = PaperBrokerSimulator()
    loop = make_loop(tmp_path, broker)
    opened = run_open(loop)
    assert opened.allowed

    broker.clear_positions()

    result = run_open(loop, order_id="ord-2")
    assert result.action == "DENY"
    assert not result.allowed
    assert "position reconciliation" in result.reason


def test_position_volume_noise_within_tolerance_stays_reconciled(tmp_path: Path):
    broker = PaperBrokerSimulator()
    loop = make_loop(tmp_path, broker)
    opened = run_open(loop)
    assert opened.allowed

    broker.configure_volume_noise(1e-6)
    snapshot = loop.recovery()
    assert snapshot.decision is ExecutionRecoveryDecision.ALLOW


def test_tampered_audit_journal_halts_recovery(tmp_path: Path):
    loop = make_loop(tmp_path)
    opened = run_open(loop)
    assert opened.allowed

    audit_path = tmp_path / "execution.jsonl"
    contents = audit_path.read_text(encoding="utf-8")
    audit_path.write_text(contents.replace("support reclaim confirmed", "tampered", 1), encoding="utf-8")

    recovery = loop.recovery()
    assert recovery.decision is ExecutionRecoveryDecision.HALT
    assert recovery.issues


def test_invalid_entry_price_is_denied_before_broker_call(tmp_path: Path):
    loop = make_loop(tmp_path)
    bad_signal = EngineSignal(
        action=LONG,
        reason="bad precision",
        timeframe="5m",
        entry_reference=1.10005,
        stop_reference=1.0950,
        protection="SAFE",
    )

    result = loop.run_entry(
        signal=bad_signal,
        data_quality=DATA_OK,
        portfolio_risk=PORTFOLIO_OK,
        risk=RISK_OK,
        idempotency_key="idem-bad",
        client_order_id="ord-bad",
        submitted_at=NOW,
    )

    assert result.action == "DENY"
    assert not result.allowed
    assert "broker contract" in result.reason
    assert loop.broker.list_orders() == ()


def test_partial_fill_is_fail_closed_until_position_lifecycle_is_completed(tmp_path: Path):
    loop = make_loop(tmp_path, PaperBrokerSimulator(fill_fraction=0.5))

    result = run_open(loop)

    assert result.action == "HALT"
    assert not result.allowed
    assert result.order_state is not None
    assert result.order_state.value == "PARTIALLY_FILLED"
    assert "position reconciliation" in result.reason


def test_recovery_blocks_before_execution_when_audit_has_orphan_event(tmp_path: Path):
    loop = make_loop(tmp_path)
    loop.journal.append(
        event_id="orphan-1",
        event_type="ORDER_FILLED",
        client_order_id="unknown-order",
        state="FILLED",
        broker_order_id="broker-1",
        filled_quantity=1.0,
    )

    result = run_open(loop)

    assert result.action == "DENY"
    assert not result.allowed
    assert "execution recovery" in result.reason
