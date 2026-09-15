from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from adapters.mt5_feed import MT5BarFeed
from bot.config import BotConfig
from bot.service import BotService
from strategy.paper_runtime_engine import PaperRuntimeEngine, RuntimeBar, RuntimeSignal
from strategy.realtime import RealtimeMonitor


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ariatrading")


def _paper_runtime(symbol: str, timeframe: str, config: BotConfig) -> PaperRuntimeEngine:
    root = Path(os.getenv("PAPER_RUNTIME_DIR", "data/paper-runtime"))
    checkpoint = root / f"{symbol}-{timeframe}.checkpoint.json"
    return PaperRuntimeEngine(
        checkpoint_path=checkpoint,
        initial_balance=float(os.getenv("PAPER_INITIAL_BALANCE", "10000")),
        risk_fraction=config.default_risk_per_trade,
        fee_per_unit=float(os.getenv("PAPER_FEE_PER_UNIT", "0")),
    )


def _runtime_bar(bar) -> RuntimeBar:
    return RuntimeBar(
        time=bar.time.isoformat(),
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
    )


def _runtime_signal(symbol: str, evaluation) -> RuntimeSignal:
    signal = evaluation.signal
    return RuntimeSignal(
        action=signal.action,
        entry=signal.entry_reference,
        stop=signal.stop_reference,
        reason=signal.reason,
        score=None if signal.score is None else signal.score.total,
        symbol=symbol,
    )


def _run_mt5_execution(config: BotConfig) -> None:
    """Delegate DEMO/LIVE execution to the hardened MT5 runtime boundary."""
    from live.live_runtime_cli import main as live_runtime_main

    argv = [
        "--symbols", ",".join(config.symbols),
        "--mode", config.mode.upper(),
        "--timeframe", config.timeframe,
        "--risk", str(config.default_risk_per_trade),
        "--interval", os.getenv("BOT_POLL_SECONDS", "5"),
    ]
    if config.mt5_terminal_path:
        argv.extend(["--terminal-path", config.mt5_terminal_path])
    argv.extend(["--magic-number", str(config.magic_number)])
    live_runtime_main(argv)


def _run_paper(config: BotConfig) -> None:
    poll_seconds = max(1.0, float(os.getenv("BOT_POLL_SECONDS", "2")))
    lookback = max(250, int(os.getenv("BOT_LOOKBACK", "500")))
    service = BotService(config)
    feed = MT5BarFeed(terminal_path=config.mt5_terminal_path or None)
    monitors = {symbol: RealtimeMonitor(feed, symbol, config.timeframe, lookback=lookback) for symbol in config.symbols}
    runtimes = {symbol: _paper_runtime(symbol, config.timeframe, config) for symbol in config.symbols}
    pending: dict[str, RuntimeSignal] = {}

    for symbol, runtime in runtimes.items():
        if runtime.checkpoint_path.exists():
            recovered = runtime.recover()
            if not recovered.accepted and recovered.lifecycle.value == "HALT":
                service.set_state("HALT", f"paper recovery failed for {symbol}: {recovered.reason}")
                raise RuntimeError(recovered.reason)
        runtime.start()

    service.set_state("RUNNING")
    log.info("paper runtime started for %s on %s", ",".join(config.symbols), config.timeframe)
    try:
        while True:
            cycle_failed = False
            for symbol, monitor in monitors.items():
                try:
                    service.authorize_provider_call()
                    evaluation = monitor.evaluate_once()
                    if evaluation is None:
                        continue

                    closed_bar = feed.closed_bars(symbol, config.timeframe, 1)
                    if not closed_bar:
                        raise RuntimeError(f"MT5 returned no completed bar for {symbol}")
                    bar = closed_bar[-1]
                    result = runtimes[symbol].process_bar(_runtime_bar(bar), pending.pop(symbol, None))
                    service.emit(
                        "PAPER_RUNTIME",
                        {
                            "symbol": symbol,
                            "timeframe": config.timeframe,
                            "bar_time": bar.time.isoformat(),
                            "event": result.event.event_type,
                            "lifecycle": result.lifecycle.value,
                            "accepted": result.accepted,
                            "reason": result.reason,
                            "order_id": result.event.order_id,
                            "pnl": result.event.pnl,
                        },
                    )

                    pending[symbol] = _runtime_signal(symbol, evaluation)
                    signal = evaluation.signal
                    service.emit(
                        "SIGNAL",
                        {
                            "symbol": symbol,
                            "timeframe": config.timeframe,
                            "bar_time": evaluation.bar_time.isoformat(),
                            "event_id": evaluation.event_id,
                            "action": signal.action,
                            "reason": signal.reason,
                            "entry_reference": signal.entry_reference,
                            "stop_reference": signal.stop_reference,
                            "score": None if signal.score is None else signal.score.total,
                            "indicator_context": getattr(signal, "indicators", None) is not None,
                        },
                    )
                    log.info("%s %s %s paper=%s", symbol, config.timeframe, signal.action, result.event.event_type)
                except Exception as exc:
                    cycle_failed = True
                    log.exception("realtime/paper evaluation failed for %s", symbol)
                    service.emit("ERROR", {"symbol": symbol, "error": str(exc)}, alert=True)

            service.heartbeat(symbols=list(config.symbols), cycle_failed=cycle_failed)
            service.set_state("DEGRADED", "one or more provider/strategy evaluations failed" if cycle_failed else "")
            if not cycle_failed:
                service.set_state("RUNNING")
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        for runtime in runtimes.values():
            runtime.stop()
        service.set_state("STOPPED", "operator interrupt")
    except Exception as exc:
        for runtime in runtimes.values():
            runtime.stop()
        service.set_state("HALT", str(exc))
        service.emit("FATAL", {"error": str(exc)}, alert=True)
        raise
    finally:
        feed.close()
        service.close()


def main() -> None:
    load_dotenv()
    config = BotConfig.from_env()

    if config.mode == "paper":
        _run_paper(config)
        return

    # DEMO and LIVE both use the same broker execution boundary. LIVE can only
    # pass BotConfig validation after the explicit Stage-1 deployment policy is armed.
    _run_mt5_execution(config)


if __name__ == "__main__":
    main()
