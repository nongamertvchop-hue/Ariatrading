"""CLI entry point for the hardened continuous MT5 runtime."""

from __future__ import annotations

import argparse
import logging
import math

from adapters.mt5_feed import MT5BarFeed
from live.control_plane import BotControlPlane
from live.execution_guard import ExecutionJournal
from live.live_runtime import DailyCircuitBreaker, LiveRuntime, RuntimeLimits
from live.mt5_executor import MT5LiveExecutor
from live.production_stage1 import ProductionStage1Policy
from live.runner import ForexLiveOrchestrator
from live.runtime_status import RuntimeStatusStore

logger = logging.getLogger("ariatrading.live_runtime_cli")


def _positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be a finite value greater than 0")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ariatrading hardened MT5 trading runtime")
    parser.add_argument("--symbols", default="EURUSD")
    parser.add_argument("--mode", choices=["DEMO", "LIVE"], default="DEMO")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--risk", type=_positive_float, default=0.0025)
    parser.add_argument("--interval", type=_positive_float, default=5.0)
    parser.add_argument("--max-tick-age", type=_positive_float, default=5.0)
    parser.add_argument("--max-spread-points", type=_positive_float, default=20.0)
    parser.add_argument("--max-daily-drawdown", type=_positive_float, default=0.01)
    parser.add_argument("--terminal-path", default="")
    parser.add_argument("--magic-number", type=int, default=8808)
    parser.add_argument("--control-path", default="data/bot_control.json")
    parser.add_argument("--status-path", default="data/bot_status.json")
    return parser


def _validate_live_startup(args: argparse.Namespace, symbols: list[str]) -> None:
    if args.mode != "LIVE":
        return
    policy = ProductionStage1Policy.from_env()
    policy.validate_symbols(symbols)
    policy.validate_runtime_limits(
        risk_per_trade=args.risk,
        max_daily_drawdown=args.max_daily_drawdown,
        max_spread_points=args.max_spread_points,
        max_tick_age_seconds=args.max_tick_age,
    )


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = build_parser().parse_args(argv)
    symbols = [value.strip().upper() for value in args.symbols.split(",") if value.strip()]
    if not symbols:
        raise SystemExit("--symbols must contain at least one symbol")
    if args.magic_number <= 0:
        raise SystemExit("--magic-number must be positive")

    try:
        _validate_live_startup(args, symbols)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    executor = MT5LiveExecutor(terminal_path=args.terminal_path or None, magic_number=args.magic_number)
    feed = None
    journal = ExecutionJournal("data/execution_journal.json")
    circuit_breaker = DailyCircuitBreaker("data/daily_circuit_breaker.json", max_drawdown_fraction=args.max_daily_drawdown)
    control = BotControlPlane(args.control_path)
    status = RuntimeStatusStore(args.status_path)

    try:
        executor.connect()
        feed = MT5BarFeed(mt5_module=executor.mt5, manage_connection=False)
        orchestrator = ForexLiveOrchestrator(
            symbols=symbols,
            mode=args.mode,
            timeframe=args.timeframe,
            risk_per_trade=args.risk,
            feed=feed,
            executor=executor,
            execution_journal=journal,
        )
        runtime = LiveRuntime(
            orchestrator=orchestrator,
            feed=feed,
            executor=executor,
            journal=journal,
            limits=RuntimeLimits(
                max_tick_age_seconds=args.max_tick_age,
                max_spread_points=args.max_spread_points,
                max_daily_drawdown_fraction=args.max_daily_drawdown,
            ),
            circuit_breaker=circuit_breaker,
            control=control,
            status=status,
        )
        logger.info("Starting hardened Ariatrading runtime: mode=%s symbols=%s control=%s status=%s", args.mode, symbols, control.read().state, args.status_path)
        runtime.run_forever(args.interval)
    finally:
        if feed is not None:
            feed.close()
        executor.disconnect()


if __name__ == "__main__":
    main()
