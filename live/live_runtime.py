"""Single continuous MT5 runtime around the strategy/execution boundary.

This module is the runtime control plane. It does not invent signals; it obtains
broker data, validates operational safety, reconciles state, and delegates the
strategy decision to ``ForexLiveOrchestrator``.
"""

from __future__ import annotations

import json
import logging
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from live.execution_guard import ExecutionJournal
from live.mt5_account import validate_account_mode
from live.mt5_executor import MT5LiveExecutor
from live.runtime_controls import (
    KillSwitch,
    RuntimeSafetyConfig,
    check_clock_skew,
    exposure_counts,
    validate_runtime_configuration,
)
from live.telemetry import RuntimeTelemetry

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

# Backwards-compatible name for existing tests/callers.
RuntimeLimits = RuntimeSafetyConfig


class DailyCircuitBreaker:
    """Persist a daily equity baseline and block new entries after drawdown."""

    def __init__(self, path: str | Path, max_drawdown_fraction: float) -> None:
        if not math.isfinite(max_drawdown_fraction) or not 0 < max_drawdown_fraction < 1:
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
        if not math.isfinite(equity) or equity <= 0:
            return False, "account equity must be finite and positive"
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).date().isoformat()
        state = self._load()
        if state.get("date") != current:
            state = {"date": current, "starting_equity": float(equity)}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        starting = float(state.get("starting_equity", 0.0))
        if not math.isfinite(starting) or starting <= 0:
            return False, "invalid starting equity in circuit-breaker state"
        drawdown = max(0.0, (starting - equity) / starting)
        if drawdown >= self.max_drawdown_fraction:
            return False, f"daily drawdown circuit breaker: {drawdown:.4%} >= {self.max_drawdown_fraction:.4%}"
        return True, "daily drawdown within limit"


class LiveRuntime:
    """Drive MT5 -> completed candles/ticks -> strategy/risk -> execution."""

    def __init__(
        self,
        *,
        orchestrator,
        feed,
        executor: MT5LiveExecutor,
        journal: ExecutionJournal,
        limits: RuntimeSafetyConfig | None = None,
        circuit_breaker: DailyCircuitBreaker | None = None,
        kill_switch: KillSwitch | None = None,
        telemetry: RuntimeTelemetry | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.feed = feed
        self.executor = executor
        self.journal = journal
        self.limits = limits or RuntimeSafetyConfig()
        self.circuit_breaker = circuit_breaker
        self.kill_switch = kill_switch
        self.telemetry = telemetry
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def preflight(self) -> None:
        """Refuse to start if the requested execution environment is inconsistent."""
        validate_runtime_configuration(
            timeframe=self.orchestrator.timeframe,
            symbols=self.orchestrator.symbols,
            config=self.limits,
        )
        if self.orchestrator.mode not in {"DEMO", "LIVE"}:
            raise RuntimeError("LiveRuntime requires DEMO or LIVE execution mode")
        ok, reason = validate_account_mode(self.executor.mt5, self.orchestrator.mode)
        if not ok:
            if self.telemetry:
                self.telemetry.heartbeat(status="BLOCKED", mode=self.orchestrator.mode, reason=reason)
                self.telemetry.event("preflight_blocked", reason=reason)
            raise RuntimeError(reason)
        if self.journal.recoverable_intents():
            reason = "execution journal contains unreconciled intents; manual reconciliation required"
            if self.telemetry:
                self.telemetry.heartbeat(status="BLOCKED", mode=self.orchestrator.mode, reason=reason)
                self.telemetry.event("preflight_blocked", reason=reason)
            raise RuntimeError(reason)
        ok, reason = self.kill_switch.check() if self.kill_switch is not None else (True, "kill switch not configured")
        if not ok:
            if self.telemetry:
                self.telemetry.heartbeat(status="BLOCKED", mode=self.orchestrator.mode, reason=reason)
                self.telemetry.event("kill_switch_engaged", reason=reason)
            raise RuntimeError(reason)

        account = self.executor.get_account_snapshot()
        if not account.trade_allowed or not account.trade_expert:
            reason = "MT5 trading permissions are not enabled"
            if self.telemetry:
                self.telemetry.heartbeat(status="BLOCKED", mode=self.orchestrator.mode, account=account.login, reason=reason)
            raise RuntimeError(reason)
        if self.circuit_breaker is not None:
            ok, reason = self.circuit_breaker.check(account.equity, self.clock())
            if not ok:
                if self.telemetry:
                    self.telemetry.heartbeat(status="BLOCKED", mode=self.orchestrator.mode, account=account.login, reason=reason)
                raise RuntimeError(reason)
        if self.telemetry:
            self.telemetry.heartbeat(status="READY", mode=self.orchestrator.mode, account=account.login)
            self.telemetry.event("preflight_passed", mode=self.orchestrator.mode, account=account.login)
        logger.info("Live runtime preflight passed: mode=%s account=%s", self.orchestrator.mode, account.login)

    def _daily_realized_loss(self) -> float:
        """Return today's realized strategy loss; history failures block the cycle."""
        now = self.clock()
        if now.tzinfo is None:
            raise RuntimeError("runtime clock must return a timezone-aware datetime")
        now = now.astimezone(timezone.utc)
        deals = self.executor.mt5.history_deals_get(
            datetime(now.year, now.month, now.day, tzinfo=timezone.utc), now
        )
        if deals is None:
            raise RuntimeError(f"MT5 deal history unavailable: {self.executor.mt5.last_error()}")
        total = 0.0
        entry_out = getattr(self.executor.mt5, "DEAL_ENTRY_OUT", 1)
        entry_out_by = getattr(self.executor.mt5, "DEAL_ENTRY_OUT_BY", 3)
        for deal in deals:
            if int(getattr(deal, "magic", 0)) != self.executor.magic_number:
                continue
            if int(getattr(deal, "entry", -1)) not in {entry_out, entry_out_by}:
                continue
            total += float(getattr(deal, "profit", 0.0))
            total += float(getattr(deal, "swap", 0.0))
            total += float(getattr(deal, "commission", 0.0))
        if not math.isfinite(total):
            raise RuntimeError("MT5 deal history contains non-finite PnL")
        return max(0.0, -total)

    def process_once(self) -> int:
        """Process one safety-gated completed-bar cycle."""
        if self.kill_switch is not None:
            ok, reason = self.kill_switch.check()
            if not ok:
                logger.error(reason)
                if self.telemetry:
                    account = self.executor.get_account_snapshot()
                    self.telemetry.heartbeat(status="BLOCKED", mode=self.orchestrator.mode, account=account.login, reason=reason)
                    self.telemetry.event("kill_switch_engaged", reason=reason, account=account.login)
                return 0

        account = self.executor.get_account_snapshot()
        if self.circuit_breaker is not None:
            ok, reason = self.circuit_breaker.check(account.equity, self.clock())
            if not ok:
                logger.error(reason)
                if self.telemetry:
                    self.telemetry.heartbeat(status="BLOCKED", mode=self.orchestrator.mode, account=account.login, reason=reason)
                    self.telemetry.event("circuit_breaker", reason=reason, account=account.login)
                return 0

        positions = self.executor.get_open_positions()
        total_positions, per_symbol = exposure_counts(positions)
        if total_positions >= self.limits.max_positions:
            reason = f"global position cap reached: {total_positions} >= {self.limits.max_positions}"
            logger.error(reason)
            if self.telemetry:
                self.telemetry.heartbeat(status="BLOCKED", mode=self.orchestrator.mode, account=account.login, reason=reason)
                self.telemetry.event("position_cap", reason=reason, account=account.login)
            return 0

        daily_loss = self._daily_realized_loss()
        processed = 0
        now = self.clock()
        if now.tzinfo is None:
            raise RuntimeError("runtime clock must return a timezone-aware datetime")
        now = now.astimezone(timezone.utc)

        for symbol in self.orchestrator.symbols:
            if per_symbol.get(symbol.upper(), 0) >= self.limits.max_positions_per_symbol:
                logger.info("%s: per-symbol position cap reached", symbol)
                continue
            try:
                bars = self.feed.closed_bars(symbol, self.orchestrator.timeframe, self.orchestrator.candle_history)
                bid, ask, tick_time = self.executor.get_current_tick(symbol)
                if bid <= 0 or ask <= 0 or ask < bid:
                    logger.warning("%s: invalid tick bid=%s ask=%s", symbol, bid, ask)
                    continue
                if tick_time.tzinfo is None:
                    raise RuntimeError("tick timestamp must be timezone-aware")

                clock_ok, clock_reason = check_clock_skew(tick_time, now, self.limits.max_clock_skew_seconds)
                if not clock_ok:
                    logger.warning("%s: %s", symbol, clock_reason)
                    if self.telemetry:
                        self.telemetry.event("clock_skew", symbol=symbol, reason=clock_reason)
                    continue
                tick_age = (now - tick_time.astimezone(timezone.utc)).total_seconds()
                if tick_age < 0:
                    logger.warning("%s: broker tick is in the future; skipping", symbol)
                    continue
                if tick_age > self.limits.max_tick_age_seconds:
                    logger.warning("%s: stale tick %.3fs", symbol, tick_age)
                    if self.telemetry:
                        self.telemetry.event("stale_tick", symbol=symbol, tick_age_seconds=tick_age)
                    continue

                contract = self.executor.get_symbol_contract(symbol)
                if not math.isfinite(contract.point) or contract.point <= 0:
                    logger.warning("%s: invalid broker point size", symbol)
                    continue
                spread_points = (ask - bid) / contract.point
                if not math.isfinite(spread_points) or spread_points > self.limits.max_spread_points:
                    logger.info("%s: spread %.1f points exceeds %.1f", symbol, spread_points, self.limits.max_spread_points)
                    if self.telemetry:
                        self.telemetry.event("spread_gate", symbol=symbol, spread_points=spread_points)
                    continue

                if not bars:
                    continue
                latest = bars[-1].time
                if latest.tzinfo is None:
                    logger.warning("%s: candle timestamp is naive", symbol)
                    continue
                latest_utc = latest.astimezone(timezone.utc)
                if latest_utc > now:
                    logger.warning("%s: latest completed candle is in the future", symbol)
                    continue
                candle_age = (now - latest_utc).total_seconds()
                max_candle_age = _TIMEFRAME_SECONDS[self.orchestrator.timeframe] + 10.0
                if candle_age < 0 or candle_age > max_candle_age:
                    logger.warning("%s: stale completed candle %.3fs", symbol, candle_age)
                    if self.telemetry:
                        self.telemetry.event("stale_candle", symbol=symbol, candle_age_seconds=candle_age)
                    continue

                self.orchestrator.process_symbol(
                    symbol=symbol,
                    bars=bars,
                    bid=bid,
                    ask=ask,
                    contract=contract,
                    equity=account.equity,
                    active_symbols=sorted({position.symbol for position in positions}),
                    daily_realized_loss=daily_loss,
                )
                processed += 1
            except Exception as exc:
                logger.exception("%s: runtime gate/cycle failed; no order sent for this symbol", symbol)
                if self.telemetry:
                    self.telemetry.event("cycle_error", symbol=symbol, error=str(exc))

        if self.telemetry:
            self.telemetry.heartbeat(status="RUNNING", mode=self.orchestrator.mode, account=account.login, processed=processed)
            self.telemetry.event("cycle_completed", account=account.login, processed=processed)
        return processed

    def run_forever(self, interval_seconds: float = 5.0) -> None:
        if not math.isfinite(interval_seconds) or interval_seconds <= 0:
            raise ValueError("interval_seconds must be finite and > 0")
        self.preflight()
        logger.info("Live runtime started; interval=%.2fs", interval_seconds)
        while True:
            started = time.monotonic()
            try:
                self.process_once()
            except KeyboardInterrupt:
                logger.info("Live runtime stopped by operator")
                if self.telemetry:
                    account = self.executor.get_account_snapshot()
                    self.telemetry.heartbeat(status="STOPPED", mode=self.orchestrator.mode, account=account.login, reason="operator interrupt")
                    self.telemetry.event("runtime_stopped", account=account.login, reason="operator interrupt")
                raise
            except Exception as exc:
                logger.exception("Live runtime cycle failed closed; no blind retry")
                if self.telemetry:
                    account = self.executor.get_account_snapshot()
                    self.telemetry.heartbeat(status="ERROR", mode=self.orchestrator.mode, account=account.login, reason=str(exc))
                    self.telemetry.event("runtime_error", account=account.login, error=str(exc))
            elapsed = time.monotonic() - started
            time.sleep(max(0.0, interval_seconds - elapsed))
