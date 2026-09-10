"""Continuous MT5 live runtime around the existing strategy/execution boundary.

The runtime is deliberately thin: it does not invent signals. It only obtains
completed candles/ticks, validates freshness and account state, reconciles the
execution journal, and delegates each symbol to ForexLiveOrchestrator.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from live.execution_guard import ExecutionJournal
from live.mt5_account import validate_account_mode
from live.mt5_executor import MT5LiveExecutor
from live.runner import ForexLiveOrchestrator
from strategy.forex_risk import ForexSymbolContract

logger = logging.getLogger("ariatrading.live_runtime")

_TIMEFRAME_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1D": 86400,
}


@dataclass(frozen=True)
class RuntimeLimits:
    """Operational limits; these are execution safeguards, not strategy rules."""

    max_tick_age_seconds: float = 10.0
    max_spread_points: float = 30.0
    max_daily_drawdown_fraction: float = 0.02


class DailyCircuitBreaker:
    """Persist a session equity baseline and stop new entries after drawdown."""

    def __init__(self, path: str | Path, max_drawdown_fraction: float) -> None:
        if not 0 < max_drawdown_fraction < 1:
            raise ValueError("max_drawdown_fraction must be between 0 and 1")
        self.path = Path(path)
        self.max_drawdown_fraction = max_drawdown_fraction

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"circuit-breaker state unreadable: {exc}") from exc
        if not isinstance(value, dict):
            raise RuntimeError("circuit-breaker state must be an object")
        return value

    def check(self, equity: float, now: datetime | None = None) -> tuple[bool, str]:
        if equity <= 0:
            return False, "account equity must be positive"
        current = (now or datetime.now(timezone.utc)).date().isoformat()
        state = self._load()
        if state.get("date") != current:
            state = {"date": current, "starting_equity": float(equity)}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        starting = float(state.get("starting_equity", 0.0))
        if starting <= 0:
            return False, "invalid starting equity in circuit-breaker state"
        drawdown = max(0.0, (starting - equity) / starting)
        if drawdown >= self.max_drawdown_fraction:
            return False, f"daily drawdown circuit breaker: {drawdown:.4%} >= {self.max_drawdown_fraction:.4%}"
        return True, "daily drawdown within limit"


class LiveRuntime:
    """Drive MT5 data -> strategy/risk -> execution for a connected terminal."""

    def __init__(
        self,
        *,
        orchestrator: ForexLiveOrchestrator,
        feed,
        executor: MT5LiveExecutor,
        journal: ExecutionJournal,
        limits: RuntimeLimits | None = None,
        circuit_breaker: DailyCircuitBreaker | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.feed = feed
        self.executor = executor
        self.journal = journal
        self.limits = limits or RuntimeLimits()
        self.circuit_breaker = circuit_breaker
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def preflight(self) -> None:
        """Refuse to start if the requested execution environment is inconsistent."""
        if self.orchestrator.mode not in {"DEMO", "LIVE"}:
            raise RuntimeError("LiveRuntime requires DEMO or LIVE execution mode")
        ok, reason = validate_account_mode(self.executor.mt5, self.orchestrator.mode)
        if not ok:
            raise RuntimeError(reason)
        if self.journal.recoverable_intents():
            raise RuntimeError("execution journal contains unreconciled intents; manual reconciliation required")

        account = self.executor.get_account_snapshot()
        if not account.trade_allowed or not account.trade_expert:
            raise RuntimeError("MT5 trading permissions are not enabled")
        if self.circuit_breaker is not None:
            ok, reason = self.circuit_breaker.check(account.equity, self.clock())
            if not ok:
                raise RuntimeError(reason)
        logger.info("Live runtime preflight passed: mode=%s account=%s", self.orchestrator.mode, account.login)

    def process_once(self) -> int:
        """Process one completed-bar cycle. Returns number of evaluated symbols."""
        account = self.executor.get_account_snapshot()
        if self.circuit_breaker is not None:
            ok, reason = self.circuit_breaker.check(account.equity, self.clock())
            if not ok:
                raise RuntimeError(reason)

        positions = self.executor.get_open_positions()
        active_symbols = sorted({position.symbol for position in positions})
        processed = 0
        now = self.clock()

        for symbol in self.orchestrator.symbols:
            bars = self.feed.closed_bars(symbol, self.orchestrator.timeframe, self.orchestrator.candle_history)
            bid, ask, tick_time = self.executor.get_current_tick(symbol)
            if bid <= 0 or ask <= 0 or ask < bid:
                logger.warning("%s: invalid tick bid=%s ask=%s", symbol, bid, ask)
                continue
            tick_age = (now - tick_time).total_seconds()
            if tick_age > self.limits.max_tick_age_seconds:
                logger.warning("%s: stale tick %.3fs", symbol, tick_age)
                continue

            contract: ForexSymbolContract = self.executor.get_symbol_contract(symbol)
            spread_points = (ask - bid) / contract.point
            if spread_points > self.limits.max_spread_points:
                logger.info("%s: spread %.1f points exceeds %.1f", symbol, spread_points, self.limits.max_spread_points)
                continue

            if not bars:
                continue
            latest = bars[-1].time
            max_candle_age = _TIMEFRAME_SECONDS[self.orchestrator.timeframe] + 10.0
            candle_age = (now - latest).total_seconds()
            if candle_age > max_candle_age:
                logger.warning("%s: stale completed candle %.3fs", symbol, candle_age)
                continue

            self.orchestrator.process_symbol(
                symbol=symbol,
                bars=bars,
                bid=bid,
                ask=ask,
                contract=contract,
                equity=account.equity,
                active_symbols=active_symbols,
            )
            processed += 1
        return processed

    def run_forever(self, interval_seconds: float = 5.0) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be > 0")
        self.preflight()
        logger.info("Live runtime started; interval=%.2fs", interval_seconds)
        while True:
            started = time.monotonic()
            try:
                self.process_once()
            except KeyboardInterrupt:
                logger.info("Live runtime stopped by operator")
                raise
            except Exception:
                logger.exception("Live runtime cycle failed closed; no blind retry")
            elapsed = time.monotonic() - started
            time.sleep(max(0.0, interval_seconds - elapsed))
