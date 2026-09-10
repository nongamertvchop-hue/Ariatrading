"""CLI entry point for the hardened continuous MT5 runtime.

This module intentionally keeps ALERT_ONLY out of the live runtime. Use the
existing runner for signal-only operation; this entry point is for DEMO/LIVE
execution after the runtime preflight has passed.
"""

from __future__ import annotations

import argparse
import logging

from adapters.mt5_feed import MT5BarFeed
from live.execution_guard import ExecutionJournal
from live.live_runtime import DailyCircuitBreaker, LiveRuntime, RuntimeLimits
from live.mt5_executor import MT5LiveExecutor
from live.runner import ForexLiveOrchestrator

logger = logging.getLogger("ariatrading.live_runtime_cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ariatrading hardened MT5 live runtime")
    parser.add_argument("--symbols", default="EURUSD,GBPUSD,USDJPY", help="Comma-separated broker symbols")
    parser.add_argument("--mode", choices=["DEMO", "LIVE"], default="DEMO")
    parser.add_argument("--timeframe", default="15m", help="Candle timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1D)")
    parser.add_argument("--risk", type=float, default=0.01, help="Risk fraction per trade")
    parser.add_argument("--interval", type=float, default=5.0, help="Runtime cycle interval in seconds")
    parser.add_argument("--max-tick-age", type=float, default=10.0, help="Maximum accepted broker tick age")
    parser.add_argument("--max-spread-points", type=float, default=30.0, help="Maximum accepted spread in points")
    parser.add_argument("--max-daily-drawdown", type=float, default=0.02, help="Daily equity drawdown circuit-breaker fraction")
    return parser


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = build_parser().parse_args(argv)
    symbols = [value.strip().upper() for value in args.symbols.split(",") if value.strip()]
    if not symbols:
        raise SystemExit("--symbols must contain at least one symbol")
    if args.interval <= 0:
        raise SystemExit("--interval must be > 0")

    executor = MT5LiveExecutor()
    feed = MT5BarFeed()
    journal = ExecutionJournal("data/execution_journal.json")
    circuit_breaker = DailyCircuitBreaker(
        "data/daily_circuit_breaker.json",
        max_drawdown_fraction=args.max_daily_drawdown,
    )
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
    )

    try:
        executor.connect()
        logger.info("Starting hardened Ariatrading runtime: mode=%s symbols=%s", args.mode, symbols)
        runtime.run_forever(args.interval)
    finally:
        # run_forever also closes these resources. The explicit finally keeps
        # startup failures fail-closed if preflight rejects the environment.
        try:
            executor.disconnect()
        finally:
            feed.close()


if __name__ == "__main__":
    main()
