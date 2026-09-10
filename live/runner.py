"""Production live daemon and orchestrator for Forex trading.

Lifecycle:
1. Read completed bars and current ticks from MT5.
2. Evaluate the existing strategy and market-condition gates.
3. Size risk from the live broker contract/account.
4. In DEMO/LIVE mode, reserve an idempotent intent before sending an order.
5. Fail closed on missing execution, account mismatch, journal failure, or
   ambiguous broker responses.

LIVE is explicit and never the default. This module does not place orders until
an operator starts it with --mode LIVE and the connected MT5 account is verified
as a real, trade-enabled account.
"""

from __future__ import annotations

import argparse
import logging
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
        self.symbols = [s.strip().upper() for s in symbols if s.strip()]
        if not self.symbols:
            raise ValueError("at least one symbol is required")
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

    def warm_up(self) -> None:
        """Mark the currently closed bar as seen so a restart cannot replay it."""
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
        """Process only a newly closed bar for one symbol."""
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
            daily_realized_loss=daily_realized_loss,
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

        if self.mode not in self.EXECUTION_MODES:
            self._last_processed_bar_time[symbol] = latest_bar.time
            return candidate

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

        return candidate


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ariatrading Forex Orchestrator")
    parser.add_argument("--symbols", default="EURUSD,GBPUSD,USDJPY", help="Comma-separated broker symbols")
    parser.add_argument("--mode", choices=["ALERT_ONLY", "DEMO", "LIVE"], default="ALERT_ONLY")
    parser.add_argument("--timeframe", default="15m", help="Candle timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1D)")
    parser.add_argument("--risk", type=float, default=0.01, help="Risk fraction per trade")
    parser.add_argument("--interval", type=int, default=5, help="Polling interval in seconds")
    return parser


def _daily_realized_loss(executor: MT5LiveExecutor, equity: float) -> float:
    """Return today's realized loss as a positive number; fail closed on history errors."""
    if executor.mt5 is None:
        raise RuntimeError("MT5 module unavailable")
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    deals = executor.mt5.history_deals_get(start, now)
    if deals is None:
        raise RuntimeError(f"MT5 deal history unavailable: {executor.mt5.last_error()}")
    total = 0.0
    entry_out = getattr(executor.mt5, "DEAL_ENTRY_OUT", 1)
    entry_out_by = getattr(executor.mt5, "DEAL_ENTRY_OUT_BY", 3)
    for deal in deals:
        if int(getattr(deal, "magic", 0)) != executor.magic_number:
            continue
        if int(getattr(deal, "entry", -1)) not in {entry_out, entry_out_by}:
            continue
        total += float(getattr(deal, "profit", 0.0))
        total += float(getattr(deal, "swap", 0.0))
        total += float(getattr(deal, "commission", 0.0))
    return max(0.0, -total)


def run(orchestrator: ForexLiveOrchestrator, interval_seconds: int) -> None:
    """Run the broker-driven event loop until interrupted."""
    if orchestrator.feed is None:
        raise RuntimeError("MT5 feed is unavailable")
    if interval_seconds < 1:
        raise ValueError("interval must be >= 1 second")

    orchestrator.warm_up()
    logger.info("Ariatrading live loop started in %s mode", orchestrator.mode)
    try:
        while True:
            account = orchestrator.executor.get_account_snapshot() if orchestrator.executor else None
            equity = account.equity if account else 0.0
            if orchestrator.mode in orchestrator.EXECUTION_MODES and (account is None or not account.trade_allowed or not account.trade_expert):
                logger.error("Execution disabled: MT5 account is not trade-enabled")
                time.sleep(interval_seconds)
                continue

            positions = orchestrator.executor.get_open_positions() if orchestrator.executor else []
            active_symbols = [p.symbol for p in positions]
            daily_loss = _daily_realized_loss(orchestrator.executor, equity) if orchestrator.executor else 0.0

            for symbol in orchestrator.symbols:
                try:
                    bars = orchestrator.feed.closed_bars(symbol, orchestrator.timeframe, orchestrator.candle_history)
                    bid, ask, tick_time = orchestrator.executor.get_current_tick(symbol) if orchestrator.executor else (
                        orchestrator.feed.last_tick(symbol)["bid"],
                        orchestrator.feed.last_tick(symbol)["ask"],
                        orchestrator.feed.last_tick(symbol)["time"],
                    )
                    contract = orchestrator.executor.get_symbol_contract(symbol) if orchestrator.executor else orchestrator.feed.mt5.symbol_info(symbol)
                    if not isinstance(contract, ForexSymbolContract):
                        contract = ForexSymbolContract(
                            symbol=str(contract.name),
                            digits=int(contract.digits),
                            point=float(contract.point),
                            trade_tick_value=float(contract.trade_tick_value),
                            trade_tick_size=float(contract.trade_tick_size),
                            volume_min=float(contract.volume_min),
                            volume_max=float(contract.volume_max),
                            volume_step=float(contract.volume_step),
                        )
                    if tick_time > datetime.now(timezone.utc):
                        logger.warning("%s: broker tick timestamp is in the future; skipping", symbol)
                        continue
                    orchestrator.process_symbol(
                        symbol,
                        bars,
                        bid,
                        ask,
                        contract,
                        equity,
                        active_symbols=active_symbols,
                        daily_realized_loss=daily_loss,
                    )
                except Exception:
                    logger.exception("%s: cycle failed; no order sent for this symbol", symbol)
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        logger.info("Ariatrading live loop stopped by operator")
    finally:
        if orchestrator.executor:
            orchestrator.executor.disconnect()
        if orchestrator.feed:
            orchestrator.feed.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = build_arg_parser().parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    logger.info("Starting Ariatrading Forex Runner in %s mode for symbols: %s", args.mode, symbols)

    executor = None
    if args.mode in {"DEMO", "LIVE"}:
        executor = MT5LiveExecutor()
        executor.connect()
        ok, reason = validate_account_mode(executor.mt5, args.mode)
        if not ok:
            executor.disconnect()
            raise RuntimeError(reason)
        # Bind the exact verified identity before the legacy loop can reach
        # the broker boundary. A later account switch is re-checked by the
        # executor immediately before any order operation.
        executor.bind_account_identity(executor.get_account_identity())
        logger.info("MT5 %s executor connected and account verified", args.mode)

    feed = MT5BarFeed()
    orchestrator = ForexLiveOrchestrator(
        symbols=symbols,
        mode=args.mode,
        timeframe=args.timeframe,
        risk_per_trade=args.risk,
        feed=feed,
        executor=executor,
    )
    run(orchestrator, args.interval)


if __name__ == "__main__":
    main()
