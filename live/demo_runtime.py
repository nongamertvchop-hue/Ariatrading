"""Convenience runtime for continuous MT5 demo trading.

The runtime reads a shared, persistent control-plane switch before each cycle.
A control-plane failure is fail-closed: no new demo order is allowed while the
switch state cannot be trusted.

A production deployment should run this process on a Windows host/VPS with an
installed and logged-in MetaTrader 5 terminal. The mobile device can control
this runtime through Webaria while the MT5 Python integration runs beside the
terminal.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable

from adapters.mt5_feed import MT5BarFeed
from strategy.realtime import RealtimeMonitor

from .demo_auto_trader import DemoAutoTradeResult, DemoAutoTrader, GateResolver, RiskPlanResolver
from .demo_control import DemoControlClient, DemoControlState
from .demo_mt5 import MT5DemoExecutionAdapter


class DemoRuntime:
    """Long-running closed-candle loop for demo-only automatic trading."""

    def __init__(
        self,
        *,
        symbol: str,
        timeframe: str,
        gate_resolver: GateResolver,
        risk_plan_resolver: RiskPlanResolver,
        control_url: str,
        control_token: str,
        lookback: int = 100,
        poll_seconds: float = 1.0,
        control_refresh_seconds: float = 1.0,
        heartbeat_seconds: float = 5.0,
        terminal_path: str | None = None,
        max_demo_volume: float = 0.10,
        mt5_module=None,
    ) -> None:
        if not symbol:
            raise ValueError("symbol must not be empty")
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be > 0")
        if control_refresh_seconds <= 0:
            raise ValueError("control_refresh_seconds must be > 0")
        if heartbeat_seconds <= 0:
            raise ValueError("heartbeat_seconds must be > 0")
        if lookback < 10:
            raise ValueError("lookback must be >= 10")

        self.control = DemoControlClient(control_url, control_token)
        self.feed = MT5BarFeed(mt5_module=mt5_module, terminal_path=terminal_path)
        self.executor = MT5DemoExecutionAdapter(
            self.feed.mt5,
            max_volume=max_demo_volume,
        )
        self.executor.account_snapshot()
        self.monitor = RealtimeMonitor(self.feed, symbol, timeframe, lookback=lookback)
        self.trader = DemoAutoTrader(
            self.monitor,
            self.executor,
            gate_resolver=gate_resolver,
            risk_plan_resolver=risk_plan_resolver,
            execution_enabled=self._execution_enabled,
        )
        self.poll_seconds = float(poll_seconds)
        self.control_refresh_seconds = float(control_refresh_seconds)
        self.heartbeat_seconds = float(heartbeat_seconds)
        self._running = False
        self._control_state: DemoControlState | None = None
        self._last_control_check = 0.0
        self._last_heartbeat = 0.0

    @property
    def control_state(self) -> DemoControlState | None:
        return self._control_state

    def _execution_enabled(self) -> bool:
        """Refresh control state; any error returns False."""
        try:
            self._control_state = self.control.get_state()
            self._last_control_check = time.monotonic()
            return self._control_state.enabled
        except Exception:
            self._control_state = None
            return False

    def _refresh_control_if_due(self) -> bool:
        now = time.monotonic()
        if now - self._last_control_check >= self.control_refresh_seconds:
            return self._execution_enabled()
        return self._control_state is not None and self._control_state.enabled

    def _send_heartbeat_if_due(self) -> None:
        now = time.monotonic()
        if now - self._last_heartbeat < self.heartbeat_seconds:
            return
        try:
            self._control_state = self.control.heartbeat()
        except Exception:
            # Heartbeat failure must never enable execution; retain the current
            # state only for observability until the next successful refresh.
            pass
        self._last_heartbeat = now

    def run_forever(
        self,
        *,
        on_result: Callable[[DemoAutoTradeResult], None] | None = None,
    ) -> None:
        """Run until interrupted; control/runtime ambiguity fails closed."""
        self._running = True
        try:
            self._execution_enabled()
            self._send_heartbeat_if_due()
            while self._running:
                enabled = self._refresh_control_if_due()
                self._send_heartbeat_if_due()
                if enabled:
                    try:
                        result = self.trader.process_once(now=datetime.now(timezone.utc))
                    except Exception:
                        self._running = False
                        raise
                    if result is not None and on_result is not None:
                        on_result(result)
                time.sleep(self.poll_seconds)
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the loop and close the MT5 terminal connection."""
        self._running = False
        self.executor.close()


__all__ = ["DemoRuntime"]
