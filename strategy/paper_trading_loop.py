"""End-to-end paper/demo execution coordinator.

This module intentionally stays on the paper/demo side of the boundary. It
connects an already-created strategy signal to the existing hard safety gates,
local order state machine, deterministic paper broker, position
reconciliation, execution recovery, and append-only audit journal.

No real broker API is imported or called here. A signal does not become an
order unless every pre-execution gate passes. Ambiguous submission responses
are reconciled from broker state and are never blindly retried as a new order.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from adapters.paper_broker import (
    FILLED,
    PARTIALLY_FILLED,
    REJECTED,
    LONG,
    SHORT,
    PaperBrokerSimulator,
    PaperOrderRequest,
)

from .broker_contract import SymbolContract, validate_order_contract
from .engine import EngineSignal
from .execution_audit import AuditJournal, AuditJournalError
from .execution_recovery import ExecutionRecoveryDecision, ExecutionRecoveryReport, verify_execution_recovery
from .order_state import OrderState, OrderStateMachine
from .paper_execution_conformance import RecoveryResult, submit_with_recovery
from .position_reconciliation import (
    FLAT,
    LocalPositionState,
    PositionSnapshot,
    new_entry_allowed,
    reconcile_position,
)
from .portfolio_risk import PortfolioRiskDecision
from .realtime_guard import DataQuality
from .risk_engine import RiskDecision
from .system_gate import SystemGateDecision, evaluate_system_readiness

PAPER_MODE = "PAPER"


@dataclass(frozen=True)
class PaperPosition:
    """Local position state created only after a paper fill is confirmed."""

    symbol: str
    direction: str
    quantity: float
    position_id: str
    average_entry_price: float
    entry_order_id: str

    def as_reconciliation_state(self) -> LocalPositionState:
        return LocalPositionState(
            symbol=self.symbol,
            direction=self.direction,
            quantity=self.quantity,
            position_id=self.position_id,
            average_entry_price=self.average_entry_price,
        )


@dataclass(frozen=True)
class PaperLoopResult:
    """Observable result of one end-to-end paper-loop cycle."""

    action: str
    allowed: bool
    reason: str
    client_order_id: str | None = None
    order_state: OrderState | None = None
    filled_quantity: float = 0.0
    position: PaperPosition | None = None
    reconciled: bool = False
    recovery: ExecutionRecoveryReport | None = None
    mode: str = PAPER_MODE


class PaperTradingLoop:
    """Connect strategy output to deterministic paper execution safely."""

    def __init__(
        self,
        *,
        broker: PaperBrokerSimulator,
        journal_path: str | Path,
        symbol: str,
        contract: SymbolContract,
    ) -> None:
        if contract.symbol != symbol:
            raise ValueError("contract symbol must match loop symbol")
        self.broker = broker
        self.symbol = symbol
        self.contract = contract
        self.orders = OrderStateMachine()
        self.journal = AuditJournal(journal_path)
        self.position: PaperPosition | None = None

    def recovery(self) -> ExecutionRecoveryReport:
        """Verify local order state against the durable audit journal."""
        return verify_execution_recovery(self.orders, self.journal)

    def run_entry(
        self,
        *,
        signal: EngineSignal,
        data_quality: DataQuality,
        portfolio_risk: PortfolioRiskDecision,
        risk: RiskDecision,
        reconciliation=None,
        execution_recovery: ExecutionRecoveryReport | None = None,
        ml_evidence=None,
        require_ml_evidence: bool = False,
        idempotency_key: str,
        client_order_id: str,
        submitted_at: datetime | None = None,
        value_per_price_unit: float = 1.0,
    ) -> PaperLoopResult:
        """Run one guarded paper entry from signal through position reconciliation."""
        recovery = execution_recovery if execution_recovery is not None else self.recovery()
        if reconciliation is None:
            broker_positions = self._broker_position_snapshots()
            reconciliation = reconcile_position(
                self.position.as_reconciliation_state() if self.position else None,
                broker_positions,
                broker_contract=self.contract,
            )

        gate = evaluate_system_readiness(
            signal=signal,
            data_quality=data_quality,
            portfolio_risk=portfolio_risk,
            risk=risk,
            reconciliation=reconciliation,
            execution_recovery=recovery,
            broker_contract=validate_order_contract(
                self.contract,
                symbol=self.symbol,
                price=signal.entry_reference or 0.0,
                quantity=risk.quantity,
            ) if signal.entry_reference is not None else None,
            ml_evidence=ml_evidence,
            require_ml_evidence=require_ml_evidence,
        )
        if not gate.allowed:
            return PaperLoopResult(gate.action, False, gate.reason, recovery=recovery)

        if self.position is not None:
            return PaperLoopResult("DENY", False, "paper position already exists", recovery=recovery)
        entry = signal.entry_reference
        if entry is None or signal.action not in {LONG, SHORT}:
            return PaperLoopResult("DENY", False, "signal has no executable entry reference", recovery=recovery)
        submitted_at = _ensure_utc(submitted_at or datetime.now(timezone.utc))

        request = PaperOrderRequest(
            client_order_id=client_order_id,
            symbol=self.symbol,
            direction=signal.action,
            quantity=gate.quantity,
            price=entry,
            submitted_at=submitted_at,
        )

        self._audit("ORDER_CREATED", request.client_order_id, OrderState.CREATED, reason=signal.reason)
        created = self.orders.create(
            client_order_id=request.client_order_id,
            idempotency_key=idempotency_key,
            direction=request.direction,
            quantity=request.quantity,
        )
        if not created.accepted:
            return PaperLoopResult(
                "DUPLICATE",
                True,
                created.reason,
                client_order_id=request.client_order_id,
                order_state=created.record.state,
                filled_quantity=created.record.filled_quantity,
                position=self.position,
                reconciled=True,
                recovery=self.recovery(),
            )

        self.orders.transition(request.client_order_id, OrderState.SUBMITTING)
        self._audit("ORDER_SUBMITTING", request.client_order_id, OrderState.SUBMITTING)

        try:
            broker_snapshot = self.broker.submit(request)
        except TimeoutError as exc:
            self.orders.transition(request.client_order_id, OrderState.UNKNOWN)
            self._audit("ORDER_UNKNOWN", request.client_order_id, OrderState.UNKNOWN, reason=str(exc))
            broker_snapshot = self.broker.get_order(request.client_order_id)
            if broker_snapshot is None:
                recovery = self.recovery()
                return PaperLoopResult(
                    "HALT",
                    False,
                    "submission response lost and broker order is missing",
                    client_order_id=request.client_order_id,
                    order_state=OrderState.UNKNOWN,
                    recovery=recovery,
                )
        except ConnectionError as exc:
            self.orders.transition(request.client_order_id, OrderState.UNKNOWN)
            self._audit("ORDER_UNKNOWN", request.client_order_id, OrderState.UNKNOWN, reason=str(exc))
            return PaperLoopResult(
                "HALT",
                False,
                "paper broker disconnected during submission",
                client_order_id=request.client_order_id,
                order_state=OrderState.UNKNOWN,
                recovery=self.recovery(),
            )

        try:
            result = self._apply_broker_snapshot(request.client_order_id, broker_snapshot)
        except (KeyError, RuntimeError, ValueError) as exc:
            return PaperLoopResult(
                "HALT",
                False,
                f"paper execution reconciliation failed: {exc}",
                client_order_id=request.client_order_id,
                order_state=self.orders.get(request.client_order_id).state,
                recovery=self.recovery(),
            )

        recovery = self.recovery()
        if recovery.decision is not ExecutionRecoveryDecision.ALLOW:
            return PaperLoopResult(
                "HALT",
                False,
                "execution recovery rejected post-trade state",
                client_order_id=request.client_order_id,
                order_state=result.state,
                filled_quantity=result.filled_quantity,
                recovery=recovery,
            )

        broker_positions = self._broker_position_snapshots()
        local_reconciliation = reconcile_position(
            self.position.as_reconciliation_state() if self.position else None,
            broker_positions,
            broker_contract=self.contract,
        )
        reconciled = local_reconciliation.safe
        if result.state is OrderState.FILLED:
            if len(broker_positions) != 1:
                return PaperLoopResult(
                    "HALT",
                    False,
                    "filled paper order did not produce exactly one broker position",
                    client_order_id=request.client_order_id,
                    order_state=result.state,
                    filled_quantity=result.filled_quantity,
                    recovery=recovery,
                )
            broker_position = broker_positions[0]
            broker_direction = LONG if broker_position.direction == LONG else SHORT
            self.position = PaperPosition(
                symbol=self.symbol,
                direction=broker_direction,
                quantity=broker_position.quantity,
                position_id=broker_position.position_id,
                average_entry_price=broker_position.average_entry_price or entry,
                entry_order_id=request.client_order_id,
            )
            local_reconciliation = reconcile_position(
                self.position.as_reconciliation_state(),
                broker_positions,
                broker_contract=self.contract,
            )
            reconciled = local_reconciliation.safe

        if result.state is REJECTED:
            return PaperLoopResult(
                "REJECTED",
                False,
                "paper broker rejected the order",
                client_order_id=request.client_order_id,
                order_state=result.state,
                recovery=recovery,
            )

        if not reconciled:
            return PaperLoopResult(
                "HALT",
                False,
                "position reconciliation rejected paper execution state: " + local_reconciliation.reason,
                client_order_id=request.client_order_id,
                order_state=result.state,
                filled_quantity=result.filled_quantity,
                recovery=recovery,
            )

        return PaperLoopResult(
            "OPEN" if self.position else "PARTIAL",
            True,
            "paper execution completed and reconciled",
            client_order_id=request.client_order_id,
            order_state=result.state,
            filled_quantity=result.filled_quantity,
            position=self.position,
            reconciled=True,
            recovery=recovery,
        )

    def close_position(
        self,
        *,
        price: float,
        client_order_id: str,
        idempotency_key: str,
        submitted_at: datetime | None = None,
    ) -> PaperLoopResult:
        """Close the current paper position and require post-close reconciliation."""
        if self.position is None:
            return PaperLoopResult(FLAT, True, "paper account is already flat", reconciled=True, recovery=self.recovery())
        validation = validate_order_contract(
            self.contract,
            symbol=self.symbol,
            price=price,
            quantity=self.position.quantity,
        )
        if not validation.allowed:
            return PaperLoopResult("DENY", False, "close rejected: " + validation.reason, recovery=self.recovery())

        opposite = SHORT if self.position.direction == LONG else LONG
        request = PaperOrderRequest(
            client_order_id=client_order_id,
            symbol=self.symbol,
            direction=opposite,
            quantity=self.position.quantity,
            price=price,
            submitted_at=_ensure_utc(submitted_at or datetime.now(timezone.utc)),
        )
        self._audit("CLOSE_CREATED", request.client_order_id, OrderState.CREATED)
        created = self.orders.create(
            client_order_id=client_order_id,
            idempotency_key=idempotency_key,
            direction=opposite,
            quantity=self.position.quantity,
        )
        if not created.accepted:
            return PaperLoopResult("DUPLICATE", True, created.reason, client_order_id=client_order_id, recovery=self.recovery())
        self.orders.transition(client_order_id, OrderState.SUBMITTING)
        self._audit("CLOSE_SUBMITTING", client_order_id, OrderState.SUBMITTING)
        try:
            snapshot = self.broker.submit(request)
        except (TimeoutError, ConnectionError) as exc:
            self.orders.transition(client_order_id, OrderState.UNKNOWN)
            self._audit("CLOSE_UNKNOWN", client_order_id, OrderState.UNKNOWN, reason=str(exc))
            return PaperLoopResult("HALT", False, "close response was ambiguous: " + str(exc), client_order_id=client_order_id, order_state=OrderState.UNKNOWN, recovery=self.recovery())

        result = self._apply_broker_snapshot(client_order_id, snapshot)
        if result.state is not OrderState.FILLED:
            return PaperLoopResult("HALT", False, "close did not fully fill", client_order_id=client_order_id, order_state=result.state, recovery=self.recovery())

        broker_positions = self._broker_position_snapshots()
        if broker_positions:
            reconciliation = reconcile_position(self.position.as_reconciliation_state(), broker_positions, broker_contract=self.contract)
            return PaperLoopResult("HALT", False, "position remains after close: " + reconciliation.reason, client_order_id=client_order_id, order_state=result.state, recovery=self.recovery())

        self.orders.transition(client_order_id, OrderState.CLOSED, filled_quantity=self.orders.get(client_order_id).quantity)
        self._audit("CLOSE_CLOSED", client_order_id, OrderState.CLOSED)
        self.position = None
        recovery = self.recovery()
        if recovery.decision is not ExecutionRecoveryDecision.ALLOW:
            return PaperLoopResult("HALT", False, "post-close recovery rejected state", client_order_id=client_order_id, order_state=OrderState.CLOSED, recovery=recovery)
        return PaperLoopResult("CLOSED", True, "paper position closed and reconciled", client_order_id=client_order_id, order_state=OrderState.CLOSED, reconciled=True, recovery=recovery)

    def _apply_broker_snapshot(self, client_order_id: str, snapshot) -> RecoveryResult:
        current = self.orders.get(client_order_id)
        if snapshot.status == FILLED:
            target = OrderState.FILLED
        elif snapshot.status == PARTIALLY_FILLED:
            target = OrderState.PARTIALLY_FILLED
        elif snapshot.status == REJECTED:
            target = OrderState.REJECTED
        else:
            raise RuntimeError(f"unsupported broker status {snapshot.status}")
        if current.state == target and current.filled_quantity == snapshot.filled_quantity:
            return RecoveryResult(target, current.filled_quantity, snapshot.status, False)
        transition = self.orders.transition(
            client_order_id,
            target,
            broker_order_id=client_order_id,
            filled_quantity=snapshot.filled_quantity,
        )
        if not transition.accepted:
            raise RuntimeError(transition.reason)
        self._audit(
            "ORDER_FILLED" if target is OrderState.FILLED else "ORDER_PARTIAL" if target is OrderState.PARTIALLY_FILLED else "ORDER_REJECTED",
            client_order_id,
            target,
            broker_order_id=client_order_id,
            filled_quantity=snapshot.filled_quantity,
        )
        return RecoveryResult(target, transition.record.filled_quantity, snapshot.status, False)

    def _audit(
        self,
        event_type: str,
        client_order_id: str,
        state: OrderState,
        *,
        broker_order_id: str | None = None,
        filled_quantity: float = 0.0,
        reason: str = "",
    ) -> None:
        self.journal.append(
            event_id=f"{client_order_id}:{event_type}:{_audit_sequence(self.journal)}",
            event_type=event_type,
            client_order_id=client_order_id,
            state=state.value,
            broker_order_id=broker_order_id,
            filled_quantity=filled_quantity,
            reason=reason,
        )

    def _broker_position_snapshots(self) -> list[PositionSnapshot]:
        snapshots = []
        for index, position in enumerate(self.broker.positions()):
            direction = LONG if position.net_quantity > 0 else SHORT
            snapshots.append(
                PositionSnapshot(
                    symbol=position.symbol,
                    direction=direction,
                    quantity=abs(position.net_quantity),
                    position_id=f"paper-position-{index}",
                    average_entry_price=position.average_price,
                )
            )
        return snapshots


def _audit_sequence(journal: AuditJournal) -> int:
    try:
        return len(journal.verify()) + 1
    except AuditJournalError:
        return 1


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    utc = value.astimezone(timezone.utc)
    if utc.utcoffset() != timezone.utc.utcoffset(utc):
        raise ValueError("timestamp must be UTC")
    return utc


__all__ = ["PAPER_MODE", "PaperPosition", "PaperLoopResult", "PaperTradingLoop"]
