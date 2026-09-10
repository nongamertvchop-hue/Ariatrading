"""Production live daemon and orchestrator for Forex trading.

LIVE execution is explicitly gated by the selected production-stage policy.
Strategy semantics remain unchanged and all broker operations stay fail-closed.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from adapters.mt5_feed import MT5BarFeed
from live.execution_guard import ExecutionJournal, build_intent
from live.mt5_account import validate_account_mode
from live.mt5_executor import MT5LiveExecutor, ORDER_BUY, ORDER_SELL
from live.notifier import Notifier
from live.production_stage1 import ProductionStage1Policy
from live.production_stage2 import ProductionStage2Policy
from strategy.engine import EngineSignal, LONG, WAIT
from strategy.forex_conditions import ForexConditionDecision, ForexSessionConfig, check_forex_conditions
from strategy.forex_risk import ForexRiskDecision, ForexRiskLimits, ForexSymbolContract, evaluate_forex_risk
from strategy.realtime import LiveBar
from strategy.two_setups import evaluate_two_setups

logger = logging.getLogger("ariatrading.forex")


def _load_live_policy():
    stage = os.getenv("ARIATRADING_LIVE_STAGE", "0").strip()
    if stage == "1":
        return ProductionStage1Policy.from_env()
    if stage == "2":
        return ProductionStage2Policy.from_env()
    raise RuntimeError("LIVE production stage is not armed: set ARIATRADING_LIVE_STAGE to 1 or 2")


@dataclass(frozen=True)
class ForexCandidateOrder:
    symbol: str
    direction: str
    entry: float
    sl: float
    tp: float | None
    lot_size: float
    risk_amount: float
    score: float
    session: str


class ForexLiveOrchestrator:
    """Multi-symbol Forex orchestrator with a fail-closed execution boundary."""

    ALLOWED_MODES = {"ALERT_ONLY", "DEMO", "LIVE"}
    EXECUTION_MODES = {"DEMO", "LIVE"}

    def __init__(
        self,
        *,
        symbols: Sequence[str],
        mode: str = "ALERT_ONLY",
        timeframe: str = "15m",
        candle_history: int = 150,
        risk_per_trade: float = 0.01,
        feed: MT5BarFeed | None = None,
        executor: MT5LiveExecutor | None = None,
        notifier: Notifier | None = None,
        session_config: ForexSessionConfig | None = None,
        execution_journal: ExecutionJournal | None = None,
    ) -> None:
        self.symbols = [s.strip().upper() for s in symbols if s.strip()]
        if not self.symbols:
            raise ValueError("at least one symbol is required")
        self.mode = mode.upper()
        if self.mode not in self.ALLOWED_MODES:
            raise ValueError(f"Unsupported execution mode: {self.mode}")
        if self.mode == "LIVE":
            policy = _load_live_policy()
            policy.validate_symbols(self.symbols)
            if not 0 < risk_per_trade <= policy.max_risk_per_trade:
                raise RuntimeError(
                    f"LIVE Stage {policy.stage} risk exceeds policy: {risk_per_trade} > {policy.max_risk_per_trade}"
                )
        self.timeframe = timeframe
        self.candle_history = max(candle_history, 50)
        self.risk_limits = ForexRiskLimits(risk_per_trade_fraction=risk_per_trade)
        self.feed = feed
        self.executor = executor
        self.notifier = notifier or Notifier()
        self.session_config = session_config or ForexSessionConfig()
        self.execution_journal = execution_journal or ExecutionJournal(
            _PROJECT_ROOT / "data" / "execution_journal.json"
        )
        self._last_processed_bar_time: dict[str, datetime] = {}

    def warm_up(self) -> None:
        if self.feed is None:
            raise RuntimeError("MT5 feed is unavailable")
        for symbol in self.symbols:
            bars = self.feed.closed_bars(symbol, self.timeframe, self.candle_history)
            if bars:
                self._last_processed_bar_time[symbol] = bars[-1].time
                logger.info("%s warm-up at closed bar %s", symbol, bars[-1].time.isoformat())

    def process_symbol(
        self,
        symbol: str,
        bars: list[LiveBar],
        bid: float,
        ask: float,
        contract: ForexSymbolContract,
        equity: float,
        active_symbols: Sequence[str] = (),
        daily_realized_loss: float = 0.0,
    ) -> ForexCandidateOrder | None:
        if len(bars) < 30:
            return None
        latest_bar = bars[-1]
        last_time = self._last_processed_bar_time.get(symbol)
        if last_time is not None and latest_bar.time <= last_time:
            return None

        candle_dicts = [
            {"open": b.open, "high": b.high, "low": b.low, "close": b.close}
            for b in bars
        ]
        two_setups = evaluate_two_setups(candle_dicts, timeframe=self.timeframe)
        sig: EngineSignal = two_setups.signal
        if sig.action == WAIT or sig.protection != "SAFE":
            self._last_processed_bar_time[symbol] = latest_bar.time
            return None

        cond: ForexConditionDecision = check_forex_conditions(
            symbol=symbol, bid=bid, ask=ask, point=contract.point,
            timestamp=latest_bar.time, config=self.session_config,
        )
        direction_str = "BUY" if sig.action == LONG else "SELL"
        entry_price = ask if sig.action == LONG else bid
        if not cond.allowed:
            self._last_processed_bar_time[symbol] = latest_bar.time
            self.notifier.notify_rejection(symbol=symbol, direction=direction_str, reason=cond.reason)
            return None

        stop_price = sig.stop_reference
        if stop_price is None or stop_price <= 0:
            if sig.action == LONG:
                stop_price = min(c["low"] for c in candle_dicts[-5:]) - contract.point * 20
            else:
                stop_price = max(c["high"] for c in candle_dicts[-5:]) + contract.point * 20

        risk_dec: ForexRiskDecision = evaluate_forex_risk(
            equity=equity, entry=entry_price, stop=stop_price, contract=contract,
            limits=self.risk_limits, daily_realized_loss=daily_realized_loss,
            active_symbols=active_symbols,
        )
        if not risk_dec.allowed:
            self._last_processed_bar_time[symbol] = latest_bar.time
            self.notifier.notify_rejection(symbol=symbol, direction=direction_str, reason=risk_dec.reason)
            return None

        risk_dist = abs(entry_price - stop_price)
        tp_price = entry_price + 1.5 * risk_dist if sig.action == LONG else entry_price - 1.5 * risk_dist
        score_val = sig.score.total if (sig.score is not None and hasattr(sig.score, "total")) else 7.0
        candidate = ForexCandidateOrder(
            symbol=symbol, direction=direction_str, entry=entry_price,
            sl=stop_price, tp=tp_price, lot_size=risk_dec.lot_size,
            risk_amount=risk_dec.risk_amount, score=float(score_val), session=cond.current_session,
        )
        self.notifier.notify_signal(
            symbol=candidate.symbol, direction=candidate.direction, entry=candidate.entry,
            sl=candidate.sl, tp=candidate.tp, risk_amount=candidate.risk_amount,
            lot_size=candidate.lot_size, score=candidate.score, session=candidate.session,
            mode=self.mode,
        )

        if self.mode not in self.EXECUTION_MODES:
            self._last_processed_bar_time[symbol] = latest_bar.time
            return candidate

        self._last_processed_bar_time[symbol] = latest_bar.time
        if self.executor is None:
            self.notifier.notify_system(
                title=f"{self.mode} Execution Blocked",
                details=f"Symbol: {candidate.symbol}\nReason: executor unavailable; fail-closed.",
                alert_level="ERROR",
            )
            return candidate

        intent = build_intent(
            symbol=candidate.symbol, direction=candidate.direction, bar_time=latest_bar.time,
            entry=candidate.entry, sl=candidate.sl, tp=candidate.tp, lot_size=candidate.lot_size,
        )
        try:
            if not self.execution_journal.reserve(intent):
                existing = self.execution_journal.get(intent.intent_id) or {}
                logger.warning("Duplicate %s execution suppressed for %s (state=%s)", self.mode, candidate.symbol, existing.get("state", "UNKNOWN"))
                return candidate
        except (OSError, RuntimeError, KeyError) as exc:
            self.notifier.notify_system(
                title=f"{self.mode} Execution Blocked",
                details=f"Symbol: {candidate.symbol}\nReason: execution journal unavailable; fail-closed.\nError: {exc}",
                alert_level="ERROR",
            )
            return candidate

        try:
            self.execution_journal.transition(intent.intent_id, "SUBMITTED")
            exec_res = self.executor.send_market_order(
                symbol=candidate.symbol,
                direction=ORDER_BUY if candidate.direction == "BUY" else ORDER_SELL,
                volume=candidate.lot_size, sl=candidate.sl, tp=candidate.tp,
                comment=f"Aria-{self.mode}-{intent.intent_id[:12]}",
            )
        except Exception as exc:
            self.execution_journal.transition(intent.intent_id, "AMBIGUOUS", error=str(exc))
            self.notifier.notify_system(
                title=f"{self.mode} Order Ambiguous",
                details=f"Symbol: {candidate.symbol}\nIntent: {intent.intent_id}\nReason: {exc}\nManual reconciliation required before retry.",
                alert_level="ERROR",
            )
            return candidate

        if exec_res.success:
            self.execution_journal.transition(
                intent.intent_id, "SUCCEEDED", ticket=exec_res.ticket,
                broker_retcode=exec_res.retcode, execution_mode=self.mode,
            )
            self.notifier.notify_execution(
                symbol=candidate.symbol, direction=candidate.direction, ticket=exec_res.ticket,
                price=exec_res.price, volume=exec_res.volume, comment=exec_res.comment,
            )
        else:
            self.execution_journal.transition(
                intent.intent_id, "FAILED", broker_retcode=exec_res.retcode,
                error=exec_res.error_message, execution_mode=self.mode,
            )
            self.notifier.notify_system(
                title=f"{self.mode} Order Failed",
                details=f"Symbol: {candidate.symbol}\nError: {exec_res.error_message}",
                alert_level="ERROR",
            )
        return candidate


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ariatrading Forex Orchestrator")
    parser.add_argument("--symbols", default="EURUSD,GBPUSD,USDJPY")
    parser.add_argument("--mode", choices=["ALERT_ONLY", "DEMO", "LIVE"], default="ALERT_ONLY")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--risk", type=float, default=0.005)
    parser.add_argument("--interval", type=int, default=5)
    return parser
