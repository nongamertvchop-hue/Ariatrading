"""Persistent realtime paper-trading runtime.

The runtime is the orchestration layer that turns the previously separated
realtime monitor and paper execution components into one deterministic loop:

closed candle -> strategy signal -> readiness/risk -> paper order -> fill ->
position -> exit plan -> reconciliation -> audit -> durable checkpoint.

This module is PAPER ONLY.  It has no real broker transport and intentionally
fails closed when local state, broker state, or audit state disagree.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from adapters.paper_broker import FILLED, PARTIALLY_FILLED, REJECTED, LONG, SHORT

from .execution_recovery import ExecutionRecoveryDecision
from .order_state import OrderRecord, OrderState
from .paper_trading_loop import PAPER_MODE, PaperLoopResult, PaperPosition, PaperTradingLoop
from .position_reconciliation import reconcile_position
from .realtime import LiveEvaluation


class RuntimeRiskProvider(Protocol):
    def __call__(self, evaluation: LiveEvaluation):
        """Return (portfolio_risk_decision, trade_risk_decision)."""


@dataclass(frozen=True)
class RuntimeEvent:
    event_id: str
    event_type: str
    timestamp: str
    bar_time: str | None
    action: str
    state: str
    reason: str
    client_order_id: str | None = None
    filled_quantity: float = 0.0


@dataclass(frozen=True)
class RuntimeSnapshot:
    schema: int
    mode: str
    symbol: str
    timeframe: str
    halted: bool
    halt_reason: str
    last_bar_time: str | None
    pending_bar_time: str | None
    stop_price: float | None
    target_price: float | None
    position: dict | None
    orders: list[dict]
    events: list[dict]


@dataclass(frozen=True)
class RuntimeCycleResult:
    status: str
    reason: str
    evaluation: LiveEvaluation | None
    execution: PaperLoopResult | None
    event: RuntimeEvent | None


class JsonRuntimeStore:
    """Atomic JSON checkpoint store suitable for process restart."""

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)

    def load(self) -> RuntimeSnapshot | None:
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("schema") != 1:
                raise ValueError("unsupported runtime checkpoint schema")
            return RuntimeSnapshot(**data)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise RuntimeError(f"paper runtime checkpoint is invalid: {exc}") from exc

    def save(self, snapshot: RuntimeSnapshot) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(asdict(snapshot), sort_keys=True, separators=(",", ":"))
        fd, tmp_name = tempfile.mkstemp(prefix=".paper-runtime-", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        except OSError as exc:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise RuntimeError(f"failed to persist paper runtime checkpoint: {exc}") from exc


class PaperTradingRuntime:
    """Drive the complete paper lifecycle from newly closed realtime candles."""

    def __init__(
        self,
        *,
        monitor,
        loop: PaperTradingLoop,
        state_path: str | os.PathLike[str],
        risk_provider: RuntimeRiskProvider,
        exit_policy: Callable[[LiveEvaluation, PaperPosition, float | None, float | None], tuple[float, str] | None] | None = None,
    ) -> None:
        self.monitor = monitor
        self.loop = loop
        self.store = JsonRuntimeStore(state_path)
        self.risk_provider = risk_provider
        self.exit_policy = exit_policy or default_exit_policy
        self.halted = False
        self.halt_reason = ""
        self.pending_bar_time: datetime | None = None
        self.stop_price: float | None = None
        self.target_price: float | None = None
        self.events: list[RuntimeEvent] = []
        self._restored = False

    @property
    def mode(self) -> str:
        return PAPER_MODE

    @property
    def last_bar_time(self) -> datetime | None:
        return self.monitor.last_bar_time

    def start(self) -> RuntimeCycleResult:
        """Restore durable state and reconcile with the current paper broker."""
        if self._restored:
            return RuntimeCycleResult("READY", "runtime already restored", None, None, None)
        try:
            snapshot = self.store.load()
            if snapshot is not None:
                self._restore_snapshot(snapshot)
            self._recover_unknown_orders()
            self._reconcile_position_or_halt()
            recovery = self.loop.recovery()
            if recovery.decision is not ExecutionRecoveryDecision.ALLOW:
                return self._halt("execution recovery blocked startup: " + "; ".join(recovery.issues))
        except (ConnectionError, RuntimeError, ValueError, KeyError) as exc:
            return self._halt(f"startup recovery failed: {exc}")
        self._restored = True
        self._persist()
        return RuntimeCycleResult("READY", "paper runtime ready", None, None, None)

    def tick(self, now: datetime | None = None) -> RuntimeCycleResult:
        if not self._restored:
            ready = self.start()
            if ready.status != "READY":
                return ready
        if self.halted:
            return RuntimeCycleResult("HALT", self.halt_reason, None, None, None)

        try:
            evaluation = self.monitor.evaluate_once(now=now)
        except (RuntimeError, ValueError, ConnectionError) as exc:
            return self._halt(f"realtime feed failure: {exc}")
        if evaluation is None:
            return RuntimeCycleResult("NO_UPDATE", "no new closed candle", None, None, None)

        if self.pending_bar_time is not None and evaluation.bar_time <= self.pending_bar_time:
            return RuntimeCycleResult("NO_UPDATE", "duplicate runtime candle", evaluation, None, None)

        execution: PaperLoopResult | None = None
        event: RuntimeEvent | None = None

        if self.loop.position is not None:
            exit_decision = self.exit_policy(evaluation, self.loop.position, self.stop_price, self.target_price)
            if exit_decision is not None:
                exit_price, reason = exit_decision
                execution = self.loop.close_position(
                    price=exit_price,
                    client_order_id=f"exit-{self.loop.position.entry_order_id}-{_stamp(evaluation.bar_time)}",
                    idempotency_key=f"exit:{self.loop.position.entry_order_id}:{_stamp(evaluation.bar_time)}",
                    submitted_at=evaluation.evaluated_at,
                )
                event = self._make_event("POSITION_CLOSE", execution, evaluation, reason)
                if execution.action == "HALT":
                    return self._halt_event(evaluation, execution, event)
                if execution.action == "CLOSED":
                    self.stop_price = None
                    self.target_price = None
                    self.pending_bar_time = evaluation.bar_time
                    self._persist()
                    return RuntimeCycleResult("CLOSED", reason, evaluation, execution, event)

        portfolio_risk, trade_risk = self.risk_provider(evaluation)
        if evaluation.signal.action not in {LONG, SHORT}:
            self.pending_bar_time = evaluation.bar_time
            self._persist()
            event = self._make_event(
                "SIGNAL_WAIT",
                PaperLoopResult("WAIT", True, evaluation.signal.reason, recovery=self.loop.recovery()),
                evaluation,
                evaluation.signal.reason,
            )
            return RuntimeCycleResult("WAIT", evaluation.signal.reason, evaluation, None, event)

        client_order_id = f"entry-{evaluation.symbol}-{_stamp(evaluation.bar_time)}"
        execution = self.loop.run_entry(
            signal=evaluation.signal,
            data_quality=evaluation.snapshot.data_quality if evaluation.snapshot is not None else None,
            portfolio_risk=portfolio_risk,
            risk=trade_risk,
            idempotency_key=f"entry:{evaluation.event_id}",
            client_order_id=client_order_id,
            submitted_at=evaluation.evaluated_at,
        )
        event = self._make_event("ENTRY_RESULT", execution, evaluation, execution.reason)
        self.pending_bar_time = evaluation.bar_time
        if execution.action == "HALT":
            return self._halt_event(evaluation, execution, event)
        if execution.position is not None and evaluation.signal.entry_reference is not None:
            self.stop_price = evaluation.signal.stop_reference
            self.target_price = _target_from_signal(evaluation)
        self._persist()
        return RuntimeCycleResult(execution.action, execution.reason, evaluation, execution, event)

    def run(self, steps: int, now: datetime | None = None) -> list[RuntimeCycleResult]:
        if steps < 1:
            raise ValueError("steps must be >= 1")
        results: list[RuntimeCycleResult] = []
        for _ in range(steps):
            result = self.tick(now=now)
            results.append(result)
            if result.status == "HALT":
                break
            if result.status == "NO_UPDATE":
                break
        return results

    def snapshot(self) -> RuntimeSnapshot:
        position = None
        if self.loop.position is not None:
            position = {
                "symbol": self.loop.position.symbol,
                "direction": self.loop.position.direction,
                "quantity": self.loop.position.quantity,
                "position_id": self.loop.position.position_id,
                "average_entry_price": self.loop.position.average_entry_price,
                "entry_order_id": self.loop.position.entry_order_id,
            }
        orders = [asdict(record) | {"state": record.state.value} for record in self.loop.orders.all_orders()]
        last_bar = self.last_bar_time.isoformat().replace("+00:00", "Z") if self.last_bar_time else None
        pending = self.pending_bar_time.isoformat().replace("+00:00", "Z") if self.pending_bar_time else None
        return RuntimeSnapshot(
            schema=1,
            mode=PAPER_MODE,
            symbol=self.loop.symbol,
            timeframe=self.monitor.timeframe,
            halted=self.halted,
            halt_reason=self.halt_reason,
            last_bar_time=last_bar,
            pending_bar_time=pending,
            stop_price=self.stop_price,
            target_price=self.target_price,
            position=position,
            orders=orders,
            events=[asdict(event) for event in self.events[-200:]],
        )

    def _restore_snapshot(self, snapshot: RuntimeSnapshot) -> None:
        if snapshot.mode != PAPER_MODE:
            raise ValueError("only PAPER runtime checkpoints are supported")
        if snapshot.symbol != self.loop.symbol or snapshot.timeframe != self.monitor.timeframe:
            raise ValueError("runtime checkpoint symbol/timeframe mismatch")
        for raw in snapshot.orders:
            raw = dict(raw)
            raw["state"] = OrderState(raw["state"])
            self.loop.orders.restore(OrderRecord(**raw))
        if snapshot.position:
            p = snapshot.position
            self.loop.position = PaperPosition(
                symbol=p["symbol"],
                direction=p["direction"],
                quantity=float(p["quantity"]),
                position_id=p["position_id"],
                average_entry_price=float(p["average_entry_price"]),
                entry_order_id=p["entry_order_id"],
            )
        self.halted = bool(snapshot.halted)
        self.halt_reason = snapshot.halt_reason
        self.pending_bar_time = _parse_time(snapshot.pending_bar_time)
        self.stop_price = snapshot.stop_price
        self.target_price = snapshot.target_price
        self.events = [RuntimeEvent(**raw) for raw in snapshot.events[-200:]]

    def _recover_unknown_orders(self) -> None:
        for record in self.loop.orders.all_orders():
            if record.state not in {OrderState.UNKNOWN, OrderState.SUBMITTING, OrderState.ACKNOWLEDGED, OrderState.PARTIALLY_FILLED}:
                continue
            snapshot = self.loop.broker.get_order(record.client_order_id)
            if snapshot is None:
                raise RuntimeError(f"order {record.client_order_id} has no broker outcome after restart")
            target = {
                FILLED: OrderState.FILLED,
                PARTIALLY_FILLED: OrderState.PARTIALLY_FILLED,
                REJECTED: OrderState.REJECTED,
            }.get(snapshot.status)
            if target is None:
                raise RuntimeError(f"unsupported broker recovery status {snapshot.status}")
            transition = self.loop.orders.transition(
                record.client_order_id,
                target,
                broker_order_id=record.broker_order_id or record.client_order_id,
                filled_quantity=snapshot.filled_quantity,
            )
            if not transition.accepted:
                raise RuntimeError(transition.reason)
            self.loop.journal.append(
                event_id=f"{record.client_order_id}:RECOVER:{_stamp(snapshot.updated_at)}",
                event_type="ORDER_RECOVERED",
                client_order_id=record.client_order_id,
                state=target.value,
                broker_order_id=transition.record.broker_order_id,
                filled_quantity=transition.record.filled_quantity,
                reason="recovered broker outcome after runtime restart",
            )

    def _reconcile_position_or_halt(self) -> None:
        broker_positions = self.loop._broker_position_snapshots()
        reconciliation = reconcile_position(
            self.loop.position.as_reconciliation_state() if self.loop.position else None,
            broker_positions,
            broker_contract=self.loop.contract,
        )
        if not reconciliation.safe:
            raise RuntimeError(reconciliation.reason)
        if not broker_positions:
            self.loop.position = None
            self.stop_price = None
            self.target_price = None
            return
        if self.loop.position is None:
            raise RuntimeError("broker has an open position but local runtime is flat")

    def _persist(self) -> None:
        self.store.save(self.snapshot())

    def _halt(self, reason: str) -> RuntimeCycleResult:
        self.halted = True
        self.halt_reason = reason
        self._persist()
        return RuntimeCycleResult("HALT", reason, None, None, None)

    def _halt_event(self, evaluation: LiveEvaluation, execution: PaperLoopResult, event: RuntimeEvent) -> RuntimeCycleResult:
        self.halted = True
        self.halt_reason = execution.reason
        self.events.append(event)
        self._persist()
        return RuntimeCycleResult("HALT", execution.reason, evaluation, execution, event)

    def _make_event(self, event_type: str, execution: PaperLoopResult, evaluation: LiveEvaluation, reason: str) -> RuntimeEvent:
        event = RuntimeEvent(
            event_id=f"runtime:{evaluation.event_id}:{event_type}",
            event_type=event_type,
            timestamp=evaluation.evaluated_at.isoformat().replace("+00:00", "Z"),
            bar_time=evaluation.bar_time.isoformat().replace("+00:00", "Z"),
            action=execution.action,
            state=execution.order_state.value if execution.order_state is not None else (execution.position.direction if execution.position else "FLAT"),
            reason=reason,
            client_order_id=execution.client_order_id,
            filled_quantity=execution.filled_quantity,
        )
        self.events.append(event)
        self.events = self.events[-200:]
        return event


def default_exit_policy(
    evaluation: LiveEvaluation,
    position: PaperPosition,
    stop_price: float | None,
    target_price: float | None,
) -> tuple[float, str] | None:
    """Conservative stop/target policy evaluated only on completed candles."""
    if evaluation.snapshot is None:
        return None
    candle = evaluation.snapshot.candle
    if position.direction == LONG:
        if stop_price is not None and candle.low <= stop_price:
            return stop_price, "stop loss"
        if target_price is not None and candle.high >= target_price:
            return target_price, "take profit"
    else:
        if stop_price is not None and candle.high >= stop_price:
            return stop_price, "stop loss"
        if target_price is not None and candle.low <= target_price:
            return target_price, "take profit"
    return None


def _target_from_signal(evaluation: LiveEvaluation) -> float | None:
    signal = evaluation.signal
    if signal.entry_reference is None or signal.stop_reference is None:
        return None
    risk = abs(signal.entry_reference - signal.stop_reference)
    if risk <= 0:
        return None
    reward = 2.0 * risk
    return signal.entry_reference + reward if signal.action == LONG else signal.entry_reference - reward


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("runtime checkpoint timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


__all__ = [
    "JsonRuntimeStore",
    "PaperTradingRuntime",
    "RuntimeCycleResult",
    "RuntimeEvent",
    "RuntimeSnapshot",
    "default_exit_policy",
]
