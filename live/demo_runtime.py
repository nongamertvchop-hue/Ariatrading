"""Convenience runtime for continuous MT5 demo trading.

This module intentionally requires the caller to provide the existing
Ariatrading system-gate and risk-plan contracts. It therefore cannot silently
replace research safety logic with a simplified trading path.

A production deployment should run this process on a Windows host/VPS with an
installed and logged-in MetaTrader 5 terminal. The mobile device can be used
for monitoring/control, while the MT5 Python integration itself runs beside
the terminal.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable

from adapters.mt5_feed import MT5BarFeed
from strategy.realtime import RealtimeMonitor
from strategy.system_gate import SystemGateDecision

from .demo_auto_trader import DemoAutoTradeResult, DemoAutoTrader, GateResolver, RiskPlanResolver
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
        lookback: int = 100,
        poll_seconds: float = 1.0,
        terminal_path: str | None = None,
        max_demo_volume: float = 0.10,
        mt5_module=None,
    ) -> None:
        if not symbol:
            raise ValueError("symbol must not be empty")
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be > 0")
        if lookback < 10:
            raise ValueError("lookback must be >= 10")

        self.feed = MT5BarFeed(mt5_module=mt5_module, terminal_path=terminal_path)
        self.executor = MT5DemoExecutionAdapter(
            self.feed.mt5,
            max_volume=max_demo_volume,
        )
        # The feed initialized the same terminal module. Shut that connection
        # down only through the executor/feed lifecycle after the demo guard is
        # established below.
        self.executor._assert_demo_account()
        self.monitor = RealtimeMonitor(self.feed, symbol, timeframe, lookback=lookback)
        self.trader = DemoAutoTrader(
            self.monitor,
            self.executor,
            gate_resolver=gate_resolver,
            risk_plan_resolver=risk_plan_resolver,
        )
        self.poll_seconds = float(poll_seconds)
        self._running = False

    def run_forever(
        self,
        *,
        on_result: Callable[[DemoAutoTradeResult], None] | None = None,
    ) -> None:
        """Run until interrupted; unexpected execution errors fail closed."""
        self._running = True
        try:
            while self._running:
                try:
                    result = self.trader.process_once(now=datetime.now(timezone.utc))
                    if result is not None and on_result is not None:
                        on_result(result)
                except Exception:
                    # An execution/runtime ambiguity must stop the process
                    # rather than blindly retrying an order request.
                    self._running = False
                    raise
                time.sleep(self.poll_seconds)
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the loop and close the MT5 terminal connection."""
        self._running = False
        self.executor.close()


__all__ = ["DemoRuntime"]
