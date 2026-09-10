"""CLI entry point for the hardened continuous MT5 runtime."""

from __future__ import annotations

import argparse
import logging
import math
import os

from adapters.mt5_feed import MT5BarFeed
from live.execution_guard import ExecutionJournal
from live.live_runtime import DailyCircuitBreaker, LiveRuntime, RuntimeLimits
from live.mt5_executor import MT5LiveExecutor
from live.production_stage1 import ProductionStage1Policy
from live.production_stage2 import ProductionStage2Policy
from live.runner import ForexLiveOrchestrator

logger = logging.getLogger("ariatrading.live_runtime_cli")


def _positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be a finite value greater than 0")
    return parsed


def _live_policy():
    stage = os.getenv("ARIATRADING_LIVE_STAGE", "0").strip()
    if stage == "1":
        return ProductionStage1Policy.from_env()
    if stage == "2":
        return ProductionStage2Policy.from_env()
    raise RuntimeError("LIVE production stage is not armed: set ARIATRADING_LIVE_STAGE to 1 or 2")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ariatrading hardened MT5 live runtime")
    parser.add_argument("--symbols", default="EURUSD", help="Comma-separated broker symbols")
    parser.add_argument("--mode", choices=["DEMO", "LIVE"], default="DEMO")
    parser.add_argument("--timeframe", default="15m", help="Candle timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1D)")
    parser.add_argument("--risk", type=_positive_float, default=0.005, help="Risk fraction per trade")
    parser.add_argument("--interval", type=_positive_float, default=5.0, help="Runtime cycle interval in seconds")
    parser.add_argument("--max-tick-age", type=_positive_float, default=10.0, help="Maximum accepted broker tick age")
    parser.add_argument("--max-spread-points", type=_positive_float, default=30.0, help="Maximum accepted spread in points")
    parser.add_argument("--max-daily-drawdown", type=_positive_float, default=0.02, help="Daily equity drawdown circuit-breaker fraction")
    return parser


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = build_parser().parse_args(argv)
    symbols = [value.strip().upper() for value in args.symbols.split(",") if value.strip()]
    if not symbols:
        raise SystemExit("--symbols must contain at least one symbol")
    if args.interval <= 0:
        raise SystemExit("--interval must be > 0")

    policy = _live_policy() if args.mode == "LIVE" else None
    if policy is not None:
        policy.validate_symbols(symbols)
        policy.validate_runtime_limits(
            risk_per_trade=args.risk,
            max_daily_drawdown=args.max_daily_drawdown,
            max_spread_points=args.max_spread_points,
            max_tick_age_seconds=args.max_tick_age,
        )

    executor = MT5LiveExecutor()
    feed = MT5BarFeed()
    journal = ExecutionJournal("data/execution_journal.json")
    limits = RuntimeLimits(
        max_tick_age_seconds=args.max_tick_age,
        max_spread_points=args.max_spread_points,
        max_daily_drawdown_fraction=args.max_daily_drawdown,
    )
    circuit_breaker = DailyCircuitBreaker("data/daily_circuit_breaker.json", max_drawdown_fraction=limits.max_daily_drawdown_fraction)
    orchestrator = ForexLiveOrchestrator(
        symbols=symbols, mode=args.mode, timeframe=args.timeframe,
        risk_per_trade=args.risk, feed=feed, executor=executor,
        execution_journal=journal,
    )
    runtime = LiveRuntime(
        orchestrator=orchestrator, feed=feed, executor=executor, journal=journal,
        limits=limits, circuit_breaker=circuit_breaker,
    )

    try:
        executor.connect()
        runtime.run_forever(args.interval)
    finally:
        try:
            executor.disconnect()
        finally:
            feed.close()


if __name__ == "__main__":
    main()
