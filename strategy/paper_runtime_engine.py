"""Continuous closed-candle paper runtime.

This runtime is intentionally demo-only. It accepts already-created strategy
signals, never creates a new setup, never connects to a real broker, processes
each completed bar at most once, and checkpoints before/after material state
changes so restart recovery is deterministic and fail-closed.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from pathlib import Path

from .paper_accounting import PaperAccounting
from .paper_history import PaperHistoryError, PaperHistoryStore
from .paper_runtime_checkpoint import PaperCheckpointError, load_checkpoint, save_checkpoint


class RuntimeLifecycle(str, Enum):
    FLAT = "FLAT"
    OPEN = "OPEN"
    UNKNOWN = "UNKNOWN"
    HALT = "HALT"


class FailureMode(str, Enum):
    NONE = "NONE"
    TIMEOUT_AFTER_ACCEPT = "TIMEOUT_AFTER_ACCEPT"
    DISCONNECT_BEFORE_SUBMIT = "DISCONNECT_BEFORE_SUBMIT"
    REJECT = "REJECT"
    PARTIAL_FILL = "PARTIAL_FILL"
    DISAPPEAR_POSITION = "DISAPPEAR_POSITION"
    CHECKPOINT_CORRUPTION = "CHECKPOINT_CORRUPTION"
    DUPLICATE_BAR = "DUPLICATE_BAR"
    OUT_OF_ORDER_BAR = "OUT_OF_ORDER_BAR"


@dataclass(frozen=True)
class RuntimeBar:
    time: str
    open: float
    high: float
    low: float
    close: float

    def validate(self) -> None:
        values = (self.open, self.high, self.low, self.close)
        if not self.time or not all(isfinite(float(v)) for v in values):
            raise ValueError("bar requires a timestamp and finite OHLC values")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close) or self.high < self.low:
            raise ValueError("invalid OHLC geometry")


@dataclass(frozen=True)
class RuntimeSignal:
    action: str = "WAIT"
    entry: float | None = None
    stop: float | None = None
    reason: str = ""
    score: float | None = None


@dataclass(frozen=True)
class RuntimeEvent:
    sequence: int
    event_type: str
    lifecycle: str
    bar_time: str | None
    reason: str
    order_id: str | None = None
    pnl: float | None = None


@dataclass(frozen=True)
class RuntimeResult:
    accepted: bool
    lifecycle: RuntimeLifecycle
    reason: str
    event: RuntimeEvent


def _time_key(value: str) -> float:
    if not isinstance(value, str) or not value:
        raise ValueError("bar timestamp must be a non-empty string")
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).timestamp()
    except ValueError:
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError("bar timestamp must be ISO-8601 or numeric") from exc


class PaperRuntimeEngine:
    """Stateful continuous paper runtime with durable restart recovery."""

    def __init__(self, *, checkpoint_path: str | Path, initial_balance: float = 10_000.0, risk_fraction: float = 0.01, fee_per_unit: float = 0.0, history_path: str | Path | None = None) -> None:
        if not 0 < risk_fraction <= 1:
            raise ValueError("risk_fraction must be in (0, 1]")
        self.checkpoint_path = Path(checkpoint_path)
        self.history_path = Path(history_path) if history_path is not None else self.checkpoint_path.with_suffix(".history.jsonl")
        self.history = PaperHistoryStore(self.history_path)
        self.risk_fraction = float(risk_fraction)
        self.account = PaperAccounting(initial_balance=initial_balance, fee_per_unit=fee_per_unit)
        self.lifecycle = RuntimeLifecycle.FLAT
        self.running = False
        self.halt_reason = ""
        self.last_bar_time: str | None = None
        self.last_processed_bar_time: str | None = None
        self.failure_mode = FailureMode.NONE
        self.events: list[RuntimeEvent] = []
        self._sequence = 0
        self._pending_order: dict | None = None
        self._exit_levels: dict | None = None

    def start(self) -> RuntimeResult:
        if self.lifecycle is RuntimeLifecycle.HALT:
            return self._emit(False, "HALT", "runtime is halted; recover before start")
        self.running = True
        return self._emit(True, "START", "continuous paper runtime started")

    def stop(self) -> RuntimeResult:
        self.running = False
        return self._emit(True, "STOP", "continuous paper runtime stopped")

    def set_failure_mode(self, mode: FailureMode) -> None:
        self.failure_mode = FailureMode(mode)
        self._safe_persist()

    def process_bar(self, bar: RuntimeBar, signal: RuntimeSignal | dict | None = None) -> RuntimeResult:
        bar.validate()
        if not self.running:
            return self._emit(False, "NOOP", "runtime is not running")
        if self.lifecycle is RuntimeLifecycle.HALT:
            return self._emit(False, "HALT", self.halt_reason)
        current_key = _time_key(bar.time)
        if self.last_processed_bar_time is not None:
            last_key = _time_key(self.last_processed_bar_time)
            if current_key == last_key:
                return self._emit(True, "NO_UPDATE", "duplicate completed bar ignored")
            if current_key < last_key:
                return self._halt("out-of-order completed bar rejected")

        self.last_bar_time = bar.time
        if self.failure_mode is FailureMode.DISAPPEAR_POSITION and self.account.position is not None:
            return self._halt("broker position disappeared during reconciliation")

        try:
            self.account.mark(price=bar.close, bar_time=bar.time)
            if self.account.position is not None and self._exit_levels is not None:
                exit_reason = self._check_exit(bar)
                if exit_reason is not None:
                    trade = self.account.close_position(exit_price=exit_reason[0], bar_time=bar.time)
                    self._exit_levels = None
                    self.lifecycle = RuntimeLifecycle.FLAT
                    self.last_processed_bar_time = bar.time
                    self._record_history()
                    return self._emit(True, "CLOSED", exit_reason[1], pnl=trade.net_pnl)

            if self.account.position is None:
                normalized = self._normalize_signal(signal)
                if normalized.action in {"LONG", "SHORT"}:
                    return self._enter(bar, normalized)

            self.last_processed_bar_time = bar.time
            self._record_history()
            return self._emit(True, "NO_UPDATE", "no executable setup on completed bar")
        except (ValueError, RuntimeError) as exc:
            return self._halt(f"paper accounting rejected runtime state: {exc}")

    def recover(self) -> RuntimeResult:
        try:
            payload = load_checkpoint(self.checkpoint_path)
            self._restore(payload)
            self.history.verify()
        except (PaperCheckpointError, PaperHistoryError, ValueError, TypeError, KeyError) as exc:
            self.running = False
            self.lifecycle = RuntimeLifecycle.HALT
            self.halt_reason = f"checkpoint/history recovery failed: {exc}"
            return self._emit_no_persist(False, "HALT", self.halt_reason)
        if self._pending_order is not None:
            self.running = False
            self.lifecycle = RuntimeLifecycle.HALT
            self.halt_reason = "pending paper order requires explicit reconciliation after restart"
            return self._emit_no_persist(False, "HALT", self.halt_reason)
        self.lifecycle = RuntimeLifecycle.OPEN if self.account.position is not None else RuntimeLifecycle.FLAT
        self.halt_reason = ""
        self.running = False
        return self._emit(True, "RECOVERED", "checkpoint, account and long-term history restored")

    def persist(self) -> None:
        payload = {
            "version": 1,
            "risk_fraction": self.risk_fraction,
            "lifecycle": self.lifecycle.value,
            "running": self.running,
            "halt_reason": self.halt_reason,
            "last_bar_time": self.last_bar_time,
            "last_processed_bar_time": self.last_processed_bar_time,
            "failure_mode": self.failure_mode.value,
            "account": self.account.export_state(),
            "pending_order": self._pending_order,
            "exit_levels": self._exit_levels,
            "events": [asdict(event) for event in self.events[-500:]],
            "sequence": self._sequence,
        }
        save_checkpoint(payload, self.checkpoint_path)

    def _record_history(self) -> None:
        try:
            self.history.append(self.account.snapshot(), bar_time=self.last_processed_bar_time)
        except PaperHistoryError as exc:
            self.running = False
            self.lifecycle = RuntimeLifecycle.HALT
            self.halt_reason = f"paper history persistence failed: {exc}"
            raise

    def _enter(self, bar: RuntimeBar, signal: RuntimeSignal) -> RuntimeResult:
        if signal.entry is None or signal.stop is None or signal.entry <= 0 or signal.stop <= 0 or signal.entry == signal.stop:
            self.last_processed_bar_time = bar.time
            self._record_history()
            return self._emit(False, "FLAT", "invalid paper entry/stop references")
        if signal.action not in {"LONG", "SHORT"}:
            return self._emit(False, "FLAT", "unsupported paper direction")
        risk_distance = abs(signal.entry - signal.stop)
        quantity = (self.account.balance * self.risk_fraction) / risk_distance
        if not isfinite(quantity) or quantity <= 0:
            return self._halt("risk sizing produced an invalid paper quantity")
        quantity = round(quantity, 6)
        order_id = f"paper-{signal.action.lower()}-{bar.time}"
        self._pending_order = {"order_id": order_id, "bar_time": bar.time, "side": signal.action, "quantity": quantity, "entry": signal.entry}
        self.lifecycle = RuntimeLifecycle.UNKNOWN if self.failure_mode in {FailureMode.TIMEOUT_AFTER_ACCEPT, FailureMode.DISCONNECT_BEFORE_SUBMIT} else RuntimeLifecycle.FLAT
        self._safe_persist()
        if self.failure_mode is FailureMode.DISCONNECT_BEFORE_SUBMIT:
            return self._halt("submission boundary disconnected before broker acceptance")
        if self.failure_mode is FailureMode.TIMEOUT_AFTER_ACCEPT:
            return self._halt("response lost after paper acceptance; recovery required")
        if self.failure_mode is FailureMode.REJECT:
            self._pending_order = None
            self.lifecycle = RuntimeLifecycle.FLAT
            self.last_processed_bar_time = bar.time
            self._record_history()
            return self._emit(True, "REJECTED", "paper broker rejected order", order_id=order_id)
        if self.failure_mode is FailureMode.PARTIAL_FILL:
            return self._halt("partial paper fill requires explicit reconciliation")

        self._pending_order = None
        self.account.open_position(symbol="EURUSD", side=signal.action, quantity=quantity, entry_price=signal.entry, bar_time=bar.time)
        self._exit_levels = {"side": signal.action, "stop": float(signal.stop), "target": float(signal.entry + 2 * risk_distance) if signal.action == "LONG" else float(signal.entry - 2 * risk_distance)}
        self.lifecycle = RuntimeLifecycle.OPEN
        self.last_processed_bar_time = bar.time
        self._record_history()
        return self._emit(True, "OPEN", "paper order filled and position reconciled", order_id=order_id)

    @staticmethod
    def _normalize_signal(signal: RuntimeSignal | dict | None) -> RuntimeSignal:
        if signal is None:
            return RuntimeSignal()
        if isinstance(signal, RuntimeSignal):
            return signal
        if isinstance(signal, dict):
            return RuntimeSignal(action=str(signal.get("action", signal.get("signal", "WAIT"))), entry=signal.get("entry", signal.get("entry_reference")), stop=signal.get("stop", signal.get("stop_reference")), reason=str(signal.get("reason", "")), score=signal.get("score"))
        raise TypeError("signal must be RuntimeSignal, dict or None")

    def _check_exit(self, bar: RuntimeBar) -> tuple[float, str] | None:
        levels = self._exit_levels
        position = self.account.position
        if levels is None or position is None:
            return None
        stop = float(levels["stop"])
        target = float(levels["target"])
        if position.side == "LONG":
            if bar.low <= stop:
                return stop, "stop loss"
            if bar.high >= target:
                return target, "take profit"
        else:
            if bar.high >= stop:
                return stop, "stop loss"
            if bar.low <= target:
                return target, "take profit"
        return None

    def _halt(self, reason: str) -> RuntimeResult:
        self.running = False
        self.lifecycle = RuntimeLifecycle.HALT
        self.halt_reason = reason
        self._safe_persist()
        return self._emit_no_persist(False, "HALT", reason)

    def _emit(self, accepted: bool, event_type: str, reason: str, *, order_id: str | None = None, pnl: float | None = None) -> RuntimeResult:
        event = self._new_event(event_type, reason, order_id=order_id, pnl=pnl)
        self._safe_persist()
        return RuntimeResult(accepted, self.lifecycle, reason, event)

    def _emit_no_persist(self, accepted: bool, event_type: str, reason: str, *, order_id: str | None = None, pnl: float | None = None) -> RuntimeResult:
        event = self._new_event(event_type, reason, order_id=order_id, pnl=pnl)
        return RuntimeResult(accepted, self.lifecycle, reason, event)

    def _new_event(self, event_type: str, reason: str, *, order_id: str | None = None, pnl: float | None = None) -> RuntimeEvent:
        self._sequence += 1
        event = RuntimeEvent(self._sequence, event_type, self.lifecycle.value, self.last_bar_time, reason, order_id, pnl)
        self.events.append(event)
        self.events = self.events[-500:]
        return event

    def _safe_persist(self) -> None:
        try:
            self.persist()
        except PaperCheckpointError:
            self.running = False
            self.lifecycle = RuntimeLifecycle.HALT
            self.halt_reason = "runtime checkpoint persistence failed"

    def _restore(self, payload: dict) -> None:
        if payload.get("version") != 1:
            raise ValueError("unsupported checkpoint version")
        self.risk_fraction = float(payload["risk_fraction"])
        self.lifecycle = RuntimeLifecycle(payload["lifecycle"])
        self.running = bool(payload.get("running", False))
        self.halt_reason = str(payload.get("halt_reason", ""))
        self.last_bar_time = payload.get("last_bar_time")
        self.last_processed_bar_time = payload.get("last_processed_bar_time")
        self.failure_mode = FailureMode(payload.get("failure_mode", FailureMode.NONE.value))
        self.account = PaperAccounting.from_state(payload["account"])
        self._pending_order = payload.get("pending_order")
        self._exit_levels = payload.get("exit_levels")
        self.events = [RuntimeEvent(**event) for event in payload.get("events", [])]
        self._sequence = int(payload.get("sequence", 0))


__all__ = ["RuntimeLifecycle", "FailureMode", "RuntimeBar", "RuntimeSignal", "RuntimeEvent", "RuntimeResult", "PaperRuntimeEngine"]
