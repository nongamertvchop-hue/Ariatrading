"""Realtime orchestrator for MT5 demo-only automatic trading.

The orchestrator consumes the existing ``RealtimeMonitor`` output. It does not
reimplement strategy rules. A caller supplies a risk/system-gate function;
without an explicit allow decision, no broker call is made.

Execution is market-based at the first tick observed after a newly closed bar.
SL/TP are attached to the broker order using the strategy/risk plan supplied by
the caller, so the broker can protect the demo position without requiring the
Python loop to remain online for every tick.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol

from strategy.engine import LONG, SHORT
from strategy.realtime import LiveEvaluation, RealtimeMonitor
from strategy.system_gate import SystemGateDecision

from .demo_mt5 import DemoOrderResult, MT5DemoExecutionAdapter


class _Monitor(Protocol):
    def evaluate_once(self, now: datetime | None = None) -> LiveEvaluation | None: ...


RiskPlanResolver = Callable[[LiveEvaluation, float], tuple[float, float]]
GateResolver = Callable[[LiveEvaluation], SystemGateDecision]
ExecutionEnabled = Callable[[], bool]


@dataclass(frozen=True)
class DemoAutoTradeResult:
    evaluation: LiveEvaluation
    gate: SystemGateDecision | None
    order: DemoOrderResult | None
    action: str
    reason: str


class DemoAutoTrader:
    """Drive approved realtime signals into an MT5 demo account."""

    def __init__(
        self,
        monitor: RealtimeMonitor | _Monitor,
        executor: MT5DemoExecutionAdapter,
        *,
        gate_resolver: GateResolver,
        risk_plan_resolver: RiskPlanResolver,
        execution_enabled: ExecutionEnabled | None = None,
    ) -> None:
        self.monitor = monitor
        self.executor = executor
        self.gate_resolver = gate_resolver
        self.risk_plan_resolver = risk_plan_resolver
        self.execution_enabled = execution_enabled
        self._last_signal_event: tuple[str, str, datetime] | None = None

    def _control_allows_execution(self) -> bool:
        if self.execution_enabled is None:
            return True
        try:
            return bool(self.execution_enabled())
        except Exception:
            return False

    def process_once(self, now: datetime | None = None) -> DemoAutoTradeResult | None:
        """Evaluate one newly closed bar and optionally submit one demo order."""
        evaluation = self.monitor.evaluate_once(now=now)
        if evaluation is None:
            return None

        event_key = (evaluation.symbol, evaluation.timeframe, evaluation.bar_time)
        if self._last_signal_event == event_key:
            return DemoAutoTradeResult(
                evaluation=evaluation,
                gate=None,
                order=None,
                action="SKIP",
                reason="duplicate signal event",
            )
        self._last_signal_event = event_key

        signal = evaluation.signal
        if signal.action not in {LONG, SHORT}:
            return DemoAutoTradeResult(
                evaluation=evaluation,
                gate=None,
                order=None,
                action="SKIP",
                reason="signal is WAIT",
            )
        if evaluation.supervisor is None or evaluation.supervisor.action != "ALLOW":
            return DemoAutoTradeResult(
                evaluation=evaluation,
                gate=None,
                order=None,
                action="HALT",
                reason="realtime supervisor did not allow execution",
            )
        if signal.stop_reference is None or signal.zone is None:
            return DemoAutoTradeResult(
                evaluation=evaluation,
                gate=None,
                order=None,
                action="HALT",
                reason="approved signal is missing a protective stop plan",
            )

        if not self._control_allows_execution():
            return DemoAutoTradeResult(
                evaluation=evaluation,
                gate=None,
                order=None,
                action="SKIP",
                reason="demo auto trading is OFF or control plane is unavailable",
            )

        gate = self.gate_resolver(evaluation)
        if not gate.allowed:
            return DemoAutoTradeResult(
                evaluation=evaluation,
                gate=gate,
                order=None,
                action="HALT",
                reason=gate.reason,
            )
        if gate.quantity <= 0:
            return DemoAutoTradeResult(
                evaluation=evaluation,
                gate=gate,
                order=None,
                action="HALT",
                reason="system gate returned a non-positive quantity",
            )

        if self.executor.positions(evaluation.symbol):
            return DemoAutoTradeResult(
                evaluation=evaluation,
                gate=gate,
                order=None,
                action="SKIP",
                reason="ARIA-managed demo position already exists",
            )

        tick = self.executor.mt5.symbol_info_tick(evaluation.symbol)
        if tick is None:
            raise RuntimeError(f"MT5 tick request failed: {self.executor.mt5.last_error()}")
        info = self.executor.mt5.symbol_info(evaluation.symbol)
        if info is None:
            raise RuntimeError(f"MT5 symbol_info failed: {evaluation.symbol}")
        entry_price = float(tick.ask if signal.action == LONG else tick.bid)
        stop_loss, take_profit = self.risk_plan_resolver(evaluation, entry_price)

        # Re-read the control plane immediately before the irreversible broker call.
        if not self._control_allows_execution():
            return DemoAutoTradeResult(
                evaluation=evaluation,
                gate=gate,
                order=None,
                action="SKIP",
                reason="demo auto trading was switched OFF before execution",
            )

        client_order_id = self._client_order_id(evaluation)
        order = self.executor.open_market(
            client_order_id=client_order_id,
            symbol=evaluation.symbol,
            direction=signal.action,
            volume=float(gate.quantity),
            stop_loss=float(stop_loss),
            take_profit=float(take_profit),
        )
        return DemoAutoTradeResult(
            evaluation=evaluation,
            gate=gate,
            order=order,
            action="OPENED",
            reason="demo order accepted",
        )

    @staticmethod
    def _client_order_id(evaluation: LiveEvaluation) -> str:
        timestamp = evaluation.bar_time.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        action = evaluation.signal.action
        return f"ARIA-{evaluation.symbol}-{evaluation.timeframe}-{timestamp}-{action}"


__all__ = ["DemoAutoTradeResult", "DemoAutoTrader", "ExecutionEnabled", "GateResolver", "RiskPlanResolver"]
