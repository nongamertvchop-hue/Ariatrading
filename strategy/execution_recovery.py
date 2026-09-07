"""Fail-closed consistency checks for execution recovery.

This module does not place orders and does not create trading signals. It verifies
that the recovered local order snapshot agrees with the latest durable audit
record for every order, so a restart cannot silently continue from divergent
execution state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .execution_audit import AuditEvent, AuditJournal, AuditJournalError
from .order_state import OrderRecord, OrderStateMachine


class ExecutionRecoveryDecision(str, Enum):
    ALLOW = "ALLOW"
    HALT = "HALT"


@dataclass(frozen=True)
class ExecutionRecoveryReport:
    decision: ExecutionRecoveryDecision
    order_count: int
    audit_event_count: int
    checked_order_count: int
    issues: tuple[str, ...]


def _latest_events(events: tuple[AuditEvent, ...]) -> dict[str, AuditEvent]:
    latest: dict[str, AuditEvent] = {}
    for event in events:
        latest[event.client_order_id] = event
    return latest


def _compare_order(record: OrderRecord, event: AuditEvent) -> tuple[str, ...]:
    issues: list[str] = []
    if event.state != record.state.value:
        issues.append(
            f"order {record.client_order_id}: state mismatch "
            f"snapshot={record.state.value} audit={event.state}"
        )
    if event.broker_order_id != record.broker_order_id:
        issues.append(
            f"order {record.client_order_id}: broker_order_id mismatch "
            f"snapshot={record.broker_order_id!r} audit={event.broker_order_id!r}"
        )
    if float(event.filled_quantity) != float(record.filled_quantity):
        issues.append(
            f"order {record.client_order_id}: filled_quantity mismatch "
            f"snapshot={record.filled_quantity} audit={event.filled_quantity}"
        )
    return tuple(issues)


def verify_execution_recovery(
    machine: OrderStateMachine,
    journal: AuditJournal,
) -> ExecutionRecoveryReport:
    """Verify recovered order state against the durable audit journal.

    The check is intentionally fail-closed: audit corruption, missing audit
    coverage, orphan audit orders, or field mismatches all produce HALT.
    """
    orders = machine.all_orders()
    try:
        events = journal.verify()
    except AuditJournalError as exc:
        return ExecutionRecoveryReport(
            decision=ExecutionRecoveryDecision.HALT,
            order_count=len(orders),
            audit_event_count=0,
            checked_order_count=0,
            issues=(f"audit verification failed: {exc}",),
        )

    issues: list[str] = []
    latest = _latest_events(events)
    order_ids = {record.client_order_id for record in orders}

    for record in orders:
        event = latest.get(record.client_order_id)
        if event is None:
            issues.append(f"order {record.client_order_id}: missing audit event")
            continue
        issues.extend(_compare_order(record, event))

    for client_order_id in latest:
        if client_order_id not in order_ids:
            issues.append(f"audit event references unknown order {client_order_id}")

    return ExecutionRecoveryReport(
        decision=ExecutionRecoveryDecision.ALLOW if not issues else ExecutionRecoveryDecision.HALT,
        order_count=len(orders),
        audit_event_count=len(events),
        checked_order_count=len(orders),
        issues=tuple(issues),
    )


__all__ = ["ExecutionRecoveryDecision", "ExecutionRecoveryReport", "verify_execution_recovery"]
