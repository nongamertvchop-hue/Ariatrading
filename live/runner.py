"""Production live daemon and orchestrator for Forex trading.

Coordinates the multi-symbol live lifecycle:
1. Feeds: Polls completed candles from MT5 or feed adapter.
2. Signal: Evaluates Sequence, S/R Levels, and Realtime Supervisor.
3. Gates: Forex Market Conditions (Session, Rollover, Spread) + Forex Risk Sizing.
4. Action: Broadcasts alerts and routes validated orders to MT5 in DEMO/LIVE mode.

Supported modes:
- ALERT_ONLY: Monitor and send alerts without placing broker orders.
- DEMO: Execute on an MT5 demo account with hard SL/TP and slippage control.
- LIVE: Execute on an MT5 real account with the same validation/risk boundary.

The execution journal is fail-closed: an ambiguous broker response is never
retried blindly. LIVE is an explicit execution mode and is not the default.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from adapters.mt5_feed import MT5BarFeed
from live.execution_guard import ExecutionJournal, build_intent
from live.mt5_executor import MT5LiveExecutor, ORDER_BUY, ORDER_SELL
from live.notifier import Notifier
from strategy.engine import EngineSignal, LONG, WAIT
from strategy.forex_conditions import ForexConditionDecision, ForexSessionConfig, check_forex_conditions
from strategy.forex_risk import ForexRiskDecision, ForexRiskLimits, ForexSymbolContract, evaluate_forex_risk
from strategy.realtime import LiveBar
from strategy.two_setups import evaluate_two_setups

logger = logging.getLogger("ariatrading.forex")


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
        self.symbols = [s.strip().upper() for s in symbols]
        self.mode = mode.upper()
        if self.mode not in self.ALLOWED_MODES:
            raise ValueError(f"Unsupported execution mode: {self.mode}")
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

    def process_symbol(
        self,
        symbol: str,
        bars: list[LiveBar],
        bid: float,
        ask: float,
        contract: ForexSymbolContract,
        equity: float,
        active_symbols: Sequence[str] = (),
    ) -> ForexCandidateOrder | None:
        """Process completed bars and tick data for a single Forex symbol."""
        if len(bars) < 30:
            logger.debug("%s: insufficient bars (%d < 30)", symbol, len(bars))
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
            logger.debug("%s: signal is %s (protection=%s)", symbol, sig.action, sig.protection)
            return None

        cond: ForexConditionDecision = check_forex_conditions(
            symbol=symbol,
            bid=bid,
            ask=ask,
            point=contract.point,
            timestamp=latest_bar.time,
            config=self.session_config,
        )
        direction_str = "BUY" if sig.action == LONG else "SELL"
        entry_price = ask if sig.action == LONG else bid

        if not cond.allowed:
            self._last_processed_bar_time[symbol] = latest_bar.time
            logger.info("Gate rejected %s %s: %s", symbol, direction_str, cond.reason)
            self.notifier.notify_rejection(symbol=symbol, direction=direction_str, reason=cond.reason)
            return None

        stop_price = sig.stop_reference
        if stop_price is None or stop_price <= 0:
            if sig.action == LONG:
                stop_price = min(c["low"] for c in candle_dicts[-5:]) - (contract.point * 20)
            else:
                stop_price = max(c["high"] for c in candle_dicts[-5:]) + (contract.point * 20)

        risk_dec: ForexRiskDecision = evaluate_forex_risk(
            equity=equity,
            entry=entry_price,
            stop=stop_price,
            contract=contract,
            limits=self.risk_limits,
            active_symbols=active_symbols,
        )
        if not risk_dec.allowed:
            self._last_processed_bar_time[symbol] = latest_bar.time
            logger.info("Risk rejected %s %s: %s", symbol, direction_str, risk_dec.reason)
            self.notifier.notify_rejection(symbol=symbol, direction=direction_str, reason=risk_dec.reason)
            return None

        risk_dist = abs(entry_price - stop_price)
        tp_price = entry_price + (1.5 * risk_dist) if sig.action == LONG else entry_price - (1.5 * risk_dist)
        score_val = sig.score.total if (sig.score is not None and hasattr(sig.score, "total")) else 7.0
        candidate = ForexCandidateOrder(
            symbol=symbol,
            direction=direction_str,
            entry=entry_price,
            sl=stop_price,
            tp=tp_price,
            lot_size=risk_dec.lot_size,
            risk_amount=risk_dec.risk_amount,
            score=float(score_val),
            session=cond.current_session,
        )

        self.notifier.notify_signal(
            symbol=candidate.symbol,
            direction=candidate.direction,
            entry=candidate.entry,
            sl=candidate.sl,
            tp=candidate.tp,
            risk_amount=candidate.risk_amount,
            lot_size=candidate.lot_size,
            score=candidate.score,
            session=candidate.session,
            mode=self.mode,
        )

        if self.mode in self.EXECUTION_MODES:
            self._last_processed_bar_time[symbol] = latest_bar.time
            mode_label = self.mode
            if self.executor is None:
                self.notifier.notify_system(
                    title=f"{mode_label} Execution Blocked",
                    details=f"Symbol: {candidate.symbol}\nReason: executor unavailable; fail-closed.",
                    alert_level="ERROR",
                )
                return candidate

            intent = build_intent(
                symbol=candidate.symbol,
                direction=candidate.direction,
                bar_time=latest_bar.time,
                entry=candidate.entry,
                sl=candidate.sl,
                tp=candidate.tp,
                lot_size=candidate.lot_size,
            )
            try:
                if not self.execution_journal.reserve(intent):
                    existing = self.execution_journal.get(intent.intent_id) or {}
                    logger.warning(
                        "Duplicate %s execution suppressed for %s (state=%s)",
                        mode_label,
                        candidate.symbol,
                        existing.get("state", "UNKNOWN"),
                    )
                    return candidate
            except (OSError, RuntimeError, KeyError) as exc:
                logger.error("%s execution blocked: journal unavailable: %s", mode_label, exc)
                self.notifier.notify_system(
                    title=f"{mode_label} Execution Blocked",
                    details=f"Symbol: {candidate.symbol}\nReason: execution journal unavailable; fail-closed.\nError: {exc}",
                    alert_level="ERROR",
                )
                return candidate

            try:
                self.execution_journal.transition(intent.intent_id, "SUBMITTED")
                exec_res = self.executor.send_market_order(
                    symbol=candidate.symbol,
                    direction=ORDER_BUY if candidate.direction == "BUY" else ORDER_SELL,
                    volume=candidate.lot_size,
                    sl=candidate.sl,
                    tp=candidate.tp,
                    comment=f"Aria-{mode_label}-{intent.intent_id[:12]}",
                )
            except Exception as exc:
                self.execution_journal.transition(intent.intent_id, "AMBIGUOUS", error=str(exc))
                logger.exception("%s order outcome is ambiguous for %s", mode_label, candidate.symbol)
                self.notifier.notify_system(
                    title=f"{mode_label} Order Ambiguous",
                    details=f"Symbol: {candidate.symbol}\nIntent: {intent.intent_id}\nReason: {exc}\nManual reconciliation required before retry.",
                    alert_level="ERROR",
                )
                return candidate

            if exec_res.success:
                self.execution_journal.transition(
                    intent.intent_id,
                    "SUCCEEDED",
                    ticket=exec_res.ticket,
                    broker_retcode=exec_res.retcode,
                    execution_mode=mode_label,
                )
                logger.info("%s order executed #%d for %s", mode_label, exec_res.ticket, candidate.symbol)
                self.notifier.notify_execution(
                    symbol=candidate.symbol,
                    direction=candidate.direction,
                    ticket=exec_res.ticket,
                    price=exec_res.price,
                    volume=exec_res.volume,
                    comment=exec_res.comment,
                )
            else:
                self.execution_journal.transition(
                    intent.intent_id,
                    "FAILED",
                    broker_retcode=exec_res.retcode,
                    error=exec_res.error_message,
                    execution_mode=mode_label,
                )
                logger.error("%s order placement failed for %s: %s", mode_label, candidate.symbol, exec_res.error_message)
                self.notifier.notify_system(
                    title=f"{mode_label} Order Failed",
                    details=f"Symbol: {candidate.symbol}\nError: {exec_res.error_message}",
                    alert_level="ERROR",
                )
        else:
            self._last_processed_bar_time[symbol] = latest_bar.time

        return candidate


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ariatrading Forex Orchestrator")
    parser.add_argument("--symbols", default="EURUSD,GBPUSD,USDJPY", help="Comma-separated symbols")
    parser.add_argument(
        "--mode",
        choices=["ALERT_ONLY", "DEMO", "LIVE"],
        default="ALERT_ONLY",
        help="Execution mode. ALERT_ONLY never sends orders; DEMO/LIVE route through the MT5 executor.",
    )
    parser.add_argument("--timeframe", default="15m", help="Candle timeframe (1m, 5m, 15m, 1h, 4h, 1D)")
    parser.add_argument("--risk", type=float, default=0.01, help="Risk fraction per trade (default: 0.01 = 1%%)")
    parser.add_argument("--interval", type=int, default=15, help="Polling interval in seconds")
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = build_arg_parser()
    args = parser.parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    logger.info("Starting Ariatrading Forex Runner in %s mode for symbols: %s", args.mode, symbols)

    feed = None
    executor = None
    try:
        feed = MT5BarFeed()
        logger.info("MT5 feed initialized.")
    except Exception as e:
        logger.warning("MT5 feed not available (%s). Make sure MT5 terminal is open for broker feeds.", e)

    if args.mode in {"DEMO", "LIVE"}:
        try:
            executor = MT5LiveExecutor()
            executor.connect()
            logger.info("MT5 %s executor connected.", args.mode)
        except Exception as e:
            logger.error("Failed to connect MT5 %s executor: %s", args.mode, e)

    orchestrator = ForexLiveOrchestrator(
        symbols=symbols,
        mode=args.mode,
        timeframe=args.timeframe,
        risk_per_trade=args.risk,
        feed=feed,
        executor=executor,
    )
    logger.info("Forex Orchestrator initialized successfully.")


if __name__ == "__main__":
    main()
