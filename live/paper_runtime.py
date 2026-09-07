"""Automatic closed-candle paper-trading runtime.

This is the runtime boundary for the current automation phase. It continuously
polls an existing RealtimeMonitor and drives PaperSessionRunner. It never calls
MT5 order APIs and cannot place real broker orders.

The runtime is intentionally thin: strategy, data integrity, paper lifecycle,
and journaling stay in their existing modules. The runtime only coordinates
when they run and exposes a stable operational state for a future supervisor
or UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from time import sleep
from typing import Callable

from strategy.paper_session import PaperSessionResult, PaperSessionRunner
from strategy.realtime import RealtimeMonitor


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
        if self.poll_seconds <= 0:
            raise ValueError("poll_seconds must be > 0")


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

    def stop(self) -> None:
        """Request a clean stop; no new iteration is started afterwards."""
        self._stop_requested = True
        if self._state is RuntimeState.RUNNING:
            self._state = RuntimeState.STOPPED

    def step(self, now: datetime | None = None) -> PaperSessionResult | None:
        """Process exactly one closed-bar opportunity.

        Unexpected failures halt the runtime by default and are re-raised so an
        external process supervisor can observe the fault. In explicit research
        mode (``fail_closed=False``), the failure is recorded and this cycle is
        skipped; it is never reported as a successful session result.
        """
        if self._state is RuntimeState.HALTED:
            raise RuntimeError(self._last_error or "paper runtime is halted")
        if self._stop_requested:
            self._state = RuntimeState.STOPPED
            return None

        try:
            result = self.session.process_once(now=now)
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
        return self.snapshot()


__all__ = [
    "ExecutionMode",
    "RuntimeState",
    "PaperRuntimeConfig",
    "RuntimeSnapshot",
    "PaperAutomationRuntime",
]
