from pathlib import Path

from strategy.execution_audit import AuditJournal
from strategy.execution_recovery import ExecutionRecoveryDecision, verify_execution_recovery
from strategy.order_state import OrderState, OrderStateMachine


def _machine_and_journal(tmp_path: Path):
    machine = OrderStateMachine()
    created = machine.create(
        client_order_id="client-1",
        idempotency_key="idem-1",
        direction="LONG",
        quantity=2.0,
    )
    machine.transition(
        "client-1",
        OrderState.SUBMITTING,
        broker_order_id="broker-1",
    )
    machine.transition(
        "client-1",
        OrderState.ACKNOWLEDGED,
        broker_order_id="broker-1",
    )
    journal = AuditJournal(tmp_path / "audit.jsonl")
    journal.append(
        event_id="event-1",
        event_type="STATE",
        client_order_id="client-1",
        state="SUBMITTING",
        broker_order_id="broker-1",
    )
    journal.append(
        event_id="event-2",
        event_type="STATE",
        client_order_id="client-1",
        state="ACKNOWLEDGED",
        broker_order_id="broker-1",
    )
    return machine, journal


def test_recovery_allows_matching_snapshot_and_audit(tmp_path):
    machine, journal = _machine_and_journal(tmp_path)

    report = verify_execution_recovery(machine, journal)

    assert report.decision is ExecutionRecoveryDecision.ALLOW
    assert report.order_count == 1
    assert report.audit_event_count == 2
    assert report.checked_order_count == 1
    assert report.issues == ()


def test_recovery_halts_on_state_mismatch(tmp_path):
    machine, journal = _machine_and_journal(tmp_path)
    journal.append(
        event_id="event-3",
        event_type="STATE",
        client_order_id="client-1",
        state="FILLED",
        broker_order_id="broker-1",
        filled_quantity=2.0,
    )

    report = verify_execution_recovery(machine, journal)

    assert report.decision is ExecutionRecoveryDecision.HALT
    assert any("state mismatch" in issue for issue in report.issues)


def test_recovery_halts_on_missing_audit_coverage(tmp_path):
    machine = OrderStateMachine()
    machine.create(
        client_order_id="client-1",
        idempotency_key="idem-1",
        direction="SHORT",
        quantity=1.0,
    )
    journal = AuditJournal(tmp_path / "audit.jsonl")

    report = verify_execution_recovery(machine, journal)

    assert report.decision is ExecutionRecoveryDecision.HALT
    assert report.issues == ("order client-1: missing audit event",)


def test_recovery_halts_on_orphan_audit_order(tmp_path):
    machine = OrderStateMachine()
    journal = AuditJournal(tmp_path / "audit.jsonl")
    journal.append(
        event_id="event-orphan",
        event_type="STATE",
        client_order_id="orphan-client",
        state="CANCELLED",
    )

    report = verify_execution_recovery(machine, journal)

    assert report.decision is ExecutionRecoveryDecision.HALT
    assert report.issues == ("audit event references unknown order orphan-client",)


def test_recovery_halts_on_tampered_audit(tmp_path):
    machine, journal = _machine_and_journal(tmp_path)
    path = tmp_path / "audit.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[1] = lines[1].replace("ACKNOWLEDGED", "FILLED")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = verify_execution_recovery(machine, journal)

    assert report.decision is ExecutionRecoveryDecision.HALT
    assert report.audit_event_count == 0
    assert any("audit verification failed" in issue for issue in report.issues)
