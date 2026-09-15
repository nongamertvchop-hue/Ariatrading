"""Continuous MT5 live runtime around the existing strategy/execution boundary.

The runtime is deliberately thin: it does not invent signals. It only obtains
completed candles/ticks, validates freshness and account state, reconciles the
execution journal against read-only broker evidence, and delegates each symbol
to ForexLiveOrchestrator.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from live.broker_reconciliation import find_execution_evidence, is_unambiguous_execution
from live.control_plane import BotControlPlane, RUN
from live.execution_guard import ExecutionJournal
from live.mt5_account import validate_account_mode
from live.mt5_executor import AccountIdentity, MT5LiveExecutor
from live.runner import ForexLiveOrchestrator
from live.runtime_status import RuntimeStatusStore
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

    def _save(self, state: dict) -> None:
        """Atomically persist the breaker baseline so a torn write fails closed."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(state, handle, sort_keys=True, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        except OSError as exc:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise RuntimeError(f"circuit-breaker state cannot be persisted safely: {exc}") from exc

    def check(self, equity: float, now: datetime | None = None) -> tuple[bool, str]:
        if equity <= 0:
            return False, "account equity must be positive"
        current = (now or datetime.now(timezone.utc)).date().isoformat()
        state = self._load()
        if state.get("date") != current:
            state = {"date": current, "starting_equity": float(equity)}
            self._save(state)
        starting = float(state.get("starting_equity", 0.0))
        if starting <= 0:
            return False, "invalid starting equity in circuit-breaker state"
        drawdown = max(0.0, (starting - equity) / starting)
        if drawdown >= self.max_drawdown_fraction:
            return False, f"daily drawdown circuit breaker: {drawdown:.4%} >= {self.max_drawdown_fraction:.4%}"
        return True, "daily drawdown within limit"


def _require_utc(value: datetime, field_name: str) -> datetime:
    """Reject naive timestamps instead of silently interpreting them in local time."""
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise RuntimeError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc)


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
        control: BotControlPlane | None = None,
        status: RuntimeStatusStore | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.feed = feed
        self.executor = executor
        self.journal = journal
        self.limits = limits or RuntimeLimits()
        self.circuit_breaker = circuit_breaker
        self.control = control
        self.status = status
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._bound_account_identity: AccountIdentity | None = None

    def _publish_status(self, *, state: str, reason: str = "", processed: int | None = None) -> None:
        if self.status is None:
            return
        control_state = self.control.read() if self.control is not None else None
        self.status.write(
            runtime_state=state,
            reason=reason,
            mode=self.orchestrator.mode,
            symbols=list(self.orchestrator.symbols),
            timeframe=self.orchestrator.timeframe,
            processed=processed,
            control_state=None if control_state is None else control_state.state,
            control_generation=None if control_state is None else control_state.generation,
            account_login=None if self._bound_account_identity is None else self._bound_account_identity.login,
            account_server=None if self._bound_account_identity is None else self._bound_account_identity.server,
        )

    def _assert_account_identity(self) -> AccountIdentity:
        """Verify the terminal is still attached to the exact preflight account."""
        current = self.executor.get_account_identity()
        bound = self._bound_account_identity
        if bound is None:
            raise RuntimeError("MT5 account identity is not bound; preflight is required before processing")
        if current != bound:
            raise RuntimeError(
                "MT5 account identity changed during runtime: "
                f"expected login={bound.login}, server={bound.server!r}, company={bound.company!r}, "
                f"trade_mode={bound.trade_mode}; got login={current.login}, server={current.server!r}, "
                f"company={current.company!r}, trade_mode={current.trade_mode}"
            )
        return current

    def _daily_realized_loss(self, now: datetime) -> float:
        """Return today's realized loss for this strategy; fail closed on history errors."""
        mt5 = self.executor.mt5
        if mt5 is None:
            raise RuntimeError("MT5 module unavailable")
        current = _require_utc(now, "runtime clock")
        start = datetime(current.year, current.month, current.day, tzinfo=timezone.utc)
        deals = mt5.history_deals_get(start, current)
        if deals is None:
            raise RuntimeError(f"MT5 deal history unavailable: {mt5.last_error()}")

        total = 0.0
        entry_out = getattr(mt5, "DEAL_ENTRY_OUT", 1)
        entry_out_by = getattr(mt5, "DEAL_ENTRY_OUT_BY", 3)
        for deal in deals:
            if int(getattr(deal, "magic", 0)) != self.executor.magic_number:
                continue
            if int(getattr(deal, "entry", -1)) not in {entry_out, entry_out_by}:
                continue
            total += float(getattr(deal, "profit", 0.0))
            total += float(getattr(deal, "swap", 0.0))
            total += float(getattr(deal, "commission", 0.0))
        return max(0.0, -total)

    def _reconcile_unresolved(self, now: datetime) -> int:
        """Resolve only intents backed by one exact broker execution identity."""
        resolved = 0
        for record in self.journal.recoverable_intents():
            try:
                intent_id = str(record["intent_id"])
                since = _require_utc(datetime.fromisoformat(str(record["bar_time"])), "execution intent bar_time")
                evidence = find_execution_evidence(
                    mt5=self.executor.mt5,
                    magic_number=self.executor.magic_number,
                    intent_id=intent_id,
                    symbol=str(record["symbol"]),
                    direction=str(record["direction"]),
                    volume=float(record["lot_size"]),
                    since=since,
                    now=now,
                )
                if not is_unambiguous_execution(evidence):
                    continue
                self.journal.transition(
                    intent_id,
                    "SUCCEEDED",
                    reconciliation="broker_exact_match",
                    evidence=evidence,
                )
                resolved += 1
                logger.warning("Reconciled unresolved execution intent %s from exact broker evidence", intent_id)
            except (KeyError, TypeError, ValueError, RuntimeError):
                logger.exception("Execution reconciliation failed closed for unresolved intent")
                raise
        return resolved

    def preflight(self) -> None:
        """Refuse to start if the requested execution environment is inconsistent."""
        if self.orchestrator.mode not in {"DEMO", "LIVE"}:
            raise RuntimeError("LiveRuntime requires DEMO or LIVE execution mode")
        ok, reason = validate_account_mode(self.executor.mt5, self.orchestrator.mode)
        if not ok:
            raise RuntimeError(reason)

        now = _require_utc(self.clock(), "runtime clock")
        self._reconcile_unresolved(now)
        if self.journal.recoverable_intents():
            raise RuntimeError("execution journal contains unreconciled intents; broker evidence was insufficient")

        identity = self.executor.get_account_identity()
        account = self.executor.get_account_snapshot()
        if account.login != identity.login:
            raise RuntimeError("MT5 account identity changed while binding runtime")
        if not account.trade_allowed or not account.trade_expert:
            raise RuntimeError("MT5 trading permissions are not enabled")
        self.executor.bind_account_identity(identity)
        self._bound_account_identity = identity
        if self.circuit_breaker is not None:
            ok, reason = self.circuit_breaker.check(account.equity, now)
            if not ok:
                raise RuntimeError(reason)
        self._publish_status(state="READY")
        logger.info(
            "Live runtime preflight passed: mode=%s account=%s server=%s",
            self.orchestrator.mode,
            identity.login,
            identity.server,
        )

    def process_once(self) -> int:
        """Process one completed-bar cycle. Returns number of evaluated symbols."""
        identity = self._assert_account_identity()
        account = self.executor.get_account_snapshot()
        if account.login != identity.login:
            raise RuntimeError("MT5 account identity changed while reading account snapshot")
        now = _require_utc(self.clock(), "runtime clock")
        if self.circuit_breaker is not None:
            ok, reason = self.circuit_breaker.check(account.equity, now)
            if not ok:
                raise RuntimeError(reason)
        daily_realized_loss = self._daily_realized_loss(now)

        positions = self.executor.get_open_positions()
        active_symbols = sorted({position.symbol for position in positions})
        processed = 0

        for symbol in self.orchestrator.symbols:
            bars = self.feed.closed_bars(symbol, self.orchestrator.timeframe, self.orchestrator.candle_history)
            bid, ask, tick_time = self.executor.get_current_tick(symbol)
            if bid <= 0 or ask <= 0 or ask < bid:
                raise RuntimeError(f"{symbol}: invalid broker tick bid={bid} ask={ask}")
            tick_time = _require_utc(tick_time, f"{symbol} tick timestamp")
            tick_age = (now - tick_time).total_seconds()
            if tick_age < 0:
                raise RuntimeError(f"{symbol}: broker tick timestamp is in the future by {-tick_age:.3f}s")
            if tick_age > self.limits.max_tick_age_seconds:
                raise RuntimeError(f"{symbol}: stale broker tick {tick_age:.3f}s > {self.limits.max_tick_age_seconds:.3f}s")

            contract: ForexSymbolContract = self.executor.get_symbol_contract(symbol)
            if contract.point <= 0:
                raise RuntimeError(f"{symbol}: broker point must be positive")
            spread_points = (ask - bid) / contract.point
            if spread_points > self.limits.max_spread_points:
                logger.info("%s: spread %.1f points exceeds %.1f; no order", symbol, spread_points, self.limits.max_spread_points)
                continue

            if not bars:
                raise RuntimeError(f"{symbol}: broker returned no completed candles")
            latest = _require_utc(bars[-1].time, f"{symbol} candle timestamp")
            max_candle_age = _TIMEFRAME_SECONDS[self.orchestrator.timeframe] + 10.0
            candle_age = (now - latest).total_seconds()
            if candle_age < 0:
                raise RuntimeError(f"{symbol}: completed candle timestamp is in the future by {-candle_age:.3f}s")
            if candle_age > max_candle_age:
                raise RuntimeError(f"{symbol}: stale completed candle {candle_age:.3f}s > {max_candle_age:.3f}s")

            self.orchestrator.process_symbol(
                symbol=symbol,
                bars=bars,
                bid=bid,
                ask=ask,
                contract=contract,
                equity=account.equity,
                active_symbols=active_symbols,
                daily_realized_loss=daily_realized_loss,
            )
            processed += 1
        self._publish_status(state="RUNNING", processed=processed)
        return processed

    def run_forever(self, interval_seconds: float = 5.0) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be > 0")
        self.preflight()
        logger.info("Live runtime started; interval=%.2fs", interval_seconds)
        try:
            while True:
                started = time.monotonic()
                if self.control is not None:
                    state = self.control.read()
                    if state.state != RUN:
                        self._publish_status(state=state.state, reason=state.reason)
                        logger.info("bot control=%s reason=%s; waiting", state.state, state.reason)
                        time.sleep(min(interval_seconds, 2.0))
                        continue
                try:
                    self.process_once()
                except KeyboardInterrupt:
                    self._publish_status(state="STOPPED", reason="operator interrupt")
                    logger.info("Live runtime stopped by operator")
                    raise
                except Exception as exc:
                    self._publish_status(state="ERROR", reason=str(exc))
                    logger.exception("Live runtime cycle failed closed; stopping execution")
                    raise
                elapsed = time.monotonic() - started
                time.sleep(max(0.0, interval_seconds - elapsed))
        finally:
            self.executor.disconnect()
            self.feed.close()
