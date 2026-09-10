"""CLI entrypoint for the guarded MT5 runtime.

This entrypoint owns one MT5 connection and shares it between the executor and
read-only feed. It intentionally supports only DEMO/LIVE; ALERT_ONLY remains
available through the research/orchestrator runner.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from adapters.mt5_feed import MT5BarFeed
from live.execution_guard import ExecutionJournal
from live.live_runtime import DailyCircuitBreaker, LiveRuntime, RuntimeLimits
from live.mt5_account import validate_account_mode
from live.mt5_executor import MT5LiveExecutor
from live.production_stage1 import ProductionStage1Policy
from live.runner import ForexLiveOrchestrator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger("ariatrading.runtime_cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ariatrading guarded MT5 runtime")
    parser.add_argument("--symbols", default="EURUSD")
    parser.add_argument("--mode", choices=["DEMO", "LIVE"], default="DEMO")
    parser.add_argument("--timeframe", choices=["1m", "5m", "15m", "30m", "1h", "4h", "1D"], default="15m")
    parser.add_argument("--risk", type=float, default=0.0025)
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--terminal-path", default=None)
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = build_parser().parse_args()
    symbols = [value.strip().upper() for value in args.symbols.split(",") if value.strip()]
    if not symbols:
        raise SystemExit("--symbols must contain at least one symbol")

    policy = ProductionStage1Policy.from_env() if args.mode == "LIVE" else None
    if policy is not None:
        policy.validate_symbols(symbols)
        policy.validate_runtime_limits(
            risk_per_trade=args.risk,
            max_daily_drawdown=policy.max_daily_drawdown,
            max_spread_points=policy.max_spread_points,
            max_tick_age_seconds=policy.max_tick_age_seconds,
        )

    executor = MT5LiveExecutor(terminal_path=args.terminal_path)
    feed = None
    try:
        executor.connect()
        ok, reason = validate_account_mode(executor.mt5, args.mode)
        if not ok:
            raise RuntimeError(reason)

        # Borrow the executor's already-connected MT5 session. Two independent
        # initialize()/shutdown() calls can otherwise invalidate each other.
        feed = MT5BarFeed(mt5_module=executor.mt5, manage_connection=False)
        journal = ExecutionJournal(PROJECT_ROOT / "data" / "execution_journal.json")
        orchestrator = ForexLiveOrchestrator(
            symbols=symbols,
            mode=args.mode,
            timeframe=args.timeframe,
            risk_per_trade=args.risk,
            feed=feed,
            executor=executor,
            execution_journal=journal,
        )
        limits = (
            RuntimeLimits(
                max_tick_age_seconds=policy.max_tick_age_seconds,
                max_spread_points=policy.max_spread_points,
                max_daily_drawdown_fraction=policy.max_daily_drawdown,
            )
            if policy is not None
            else RuntimeLimits()
        )
        runtime = LiveRuntime(
            orchestrator=orchestrator,
            feed=feed,
            executor=executor,
            journal=journal,
            limits=limits,
            circuit_breaker=DailyCircuitBreaker(
                PROJECT_ROOT / "data" / "daily_circuit_breaker.json",
                max_drawdown_fraction=limits.max_daily_drawdown_fraction,
            ),
        )
        runtime.run_forever(args.interval)
    finally:
        # LiveRuntime performs normal shutdown. This is a defensive cleanup for
        # failures during setup or preflight before run_forever starts.
        if feed is not None:
            feed.close()
        executor.disconnect()


if __name__ == "__main__":
    main()
