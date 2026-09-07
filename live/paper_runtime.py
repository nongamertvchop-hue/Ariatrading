"""Automatic closed-candle paper-trading runtime.

This is the runtime boundary for the current automation phase. It continuously
polls an existing RealtimeMonitor and drives PaperSessionRunner. It never calls
MT5 order APIs and cannot place real broker orders.

Runtime checkpoints persist the paper/session state so a process restart does
not forget the last processed candle, pending next-bar signal, account, open
position, or journal identities.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite
from time import sleep
from typing import Callable

from live.state_store import JsonRuntimeStateStore
from strategy.paper_session import PaperSessionResult, PaperSessionRunner
from strategy.realtime import RealtimeMonitor


RUNTIME_STATE_VERSION = 1


class ExecutionMode(str, Enum):
    PAPER = "PAPER"
    DEMO = "DEMO"


class RuntimeState(str, Enum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    HALTED = "HALTED"


@dataclass(frozen=True)
class PaperRuntimeConfig:
    """Operational controls for the automatic paper loop."""

    poll_seconds: float = 1.0
    fail_closed: bool = True

    def __post_init__(self) -> None:
        if not isfinite(self.poll_seconds) or self.poll_seconds <= 0:
            raise ValueError("poll_seconds must be finite and > 0")


@dataclass(frozen=True)
class RuntimeSnapshot:
    state: RuntimeState
    mode: ExecutionMode
    last_bar_time: datetime | None
    pending_signal: bool
    balance: float
    realized_r: float
    closed_trades: int
    wins: int
    losses: int
    last_error: str | None


class PaperAutomationRuntime:
    """Drive the existing realtime -> paper path.

    ``DEMO`` is deliberately rejected because the repository has no MT5
    order-sending adapter. Unexpected failures are fail-closed by default.
    ``fail_closed=False`` is retained only as an explicit research/testing
    option; it records the failure and skips that cycle rather than silently
    treating the cycle as successful.
    """

    def __init__(
        self,
        monitor: RealtimeMonitor,
        *,
        session: PaperSessionRunner | None = None,
        config: PaperRuntimeConfig | None = None,
        mode: ExecutionMode = ExecutionMode.PAPER,
        state_store: JsonRuntimeStateStore | None = None,
    ) -> None:
        try:
            normalized_mode = ExecutionMode(mode)
        except ValueError as exc:
            raise ValueError(f"unsupported execution mode: {mode!r}") from exc
        if normalized_mode is not ExecutionMode.PAPER:
            raise RuntimeError(
                "DEMO mode is not enabled: this repository currently has no MT5 order execution adapter"
            )
        self.monitor = monitor
        self.session = session or PaperSessionRunner(monitor)
        self.config = config or PaperRuntimeConfig()
        self.mode = normalized_mode
        self.state_store = state_store
        self._state = RuntimeState.STOPPED
        self._last_error: str | None = None
        self._stop_requested = False

    @property
    def state(self) -> RuntimeState:
        return self._state

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def snapshot(self) -> RuntimeSnapshot:
        account = self.session.paper.account
        return RuntimeSnapshot(
            state=self._state,
            mode=self.mode,
            last_bar_time=self.session.last_processed_bar_time,
            pending_signal=self.session.pending_signal is not None,
            balance=account.balance,
            realized_r=account.realized_r,
            closed_trades=account.closed_trades,
            wins=account.wins,
            losses=account.losses,
            last_error=self._last_error,
        )

    def checkpoint(self) -> dict:
        """Build a versioned checkpoint without writing it."""
        return {
            "version": RUNTIME_STATE_VERSION,
            "mode": self.mode.value,
            "state": self._state.value,
            "last_error": self._last_error,
            "session": self.session.to_state(),
        }

    def save_checkpoint(self) -> None:
        """Atomically persist the current runtime state.

        A configured state store is required. Persistence failures are raised
        instead of being swallowed because continuing after an unpersisted
        state change could create duplicate paper trades after restart.
        """
        if self.state_store is None:
            raise RuntimeError("no runtime state store configured")
        self.state_store.save(self.checkpoint())

    def restore_checkpoint(self) -> RuntimeSnapshot:
        """Load and validate a checkpoint, leaving the runtime STOPPED."""
        if self.state_store is None:
            raise RuntimeError("no runtime state store configured")
        state = self.state_store.load()
        try:
            if state.get("version") != RUNTIME_STATE_VERSION:
                raise ValueError("unsupported or invalid runtime state version")
            if state.get("mode") != ExecutionMode.PAPER.value:
                raise ValueError("checkpoint execution mode is not PAPER")
            self.session.restore_state(state.get("session"))
            raw_error = state.get("last_error")
            if raw_error is not None and not isinstance(raw_error, str):
                raise ValueError("checkpoint last_error is invalid")
            self._last_error = raw_error
            self._state = RuntimeState.STOPPED
            self._stop_requested = False
        except Exception as exc:
            self._last_error = f"checkpoint restore failed: {type(exc).__name__}: {exc}"
            self._state = RuntimeState.HALTED
            raise
        return self.snapshot()

    def stop(self) -> None:
        """Request a clean stop; no new iteration is started afterwards."""
        self._stop_requested = True
        if self._state is RuntimeState.RUNNING:
            self._state = RuntimeState.STOPPED

    def step(self, now: datetime | None = None) -> PaperSessionResult | None:
        """Process exactly one closed-bar opportunity."""
        if self._state is RuntimeState.HALTED:
            raise RuntimeError(self._last_error or "paper runtime is halted")
        if self._stop_requested:
            self._state = RuntimeState.STOPPED
            return None

        try:
            result = self.session.process_once(now=now)
            # Persist after every successful state transition. This is more
            # expensive than batching but materially reduces restart ambiguity
            # during the current research/paper phase.
            if self.state_store is not None:
                self.save_checkpoint()
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
            if self.config.fail_closed:
                self._state = RuntimeState.HALTED
                raise
            return None
        return result

    def run(
        self,
        *,
        max_iterations: int | None = None,
        sleep_fn: Callable[[float], None] = sleep,
    ) -> RuntimeSnapshot:
        """Run the paper loop until stopped, halted, or iteration limit is hit."""
        if max_iterations is not None and max_iterations < 1:
            raise ValueError("max_iterations must be >= 1 when provided")
        if self._state is RuntimeState.HALTED:
            raise RuntimeError(self._last_error or "paper runtime is halted")

        self._stop_requested = False
        self._state = RuntimeState.RUNNING
        iterations = 0
        try:
            while not self._stop_requested:
                self.step()
                iterations += 1
                if max_iterations is not None and iterations >= max_iterations:
                    break
                sleep_fn(self.config.poll_seconds)
        finally:
            if self._state is RuntimeState.RUNNING:
                self._state = RuntimeState.STOPPED
                if self.state_store is not None:
                    self.save_checkpoint()
        return self.snapshot()


__all__ = [
    "ExecutionMode",
    "RuntimeState",
    "PaperRuntimeConfig",
    "RuntimeSnapshot",
    "PaperAutomationRuntime",
]
