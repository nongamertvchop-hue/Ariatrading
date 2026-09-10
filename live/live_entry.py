"""Operator-facing entrypoint for the guarded MT5 runtime.

This entrypoint is deliberately explicit: no implicit LIVE mode, no strategy
changes, and no automatic recovery of ambiguous broker outcomes.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from adapters.mt5_feed import MT5BarFeed
from live.execution_guard import ExecutionJournal
from live.live_runtime import DailyCircuitBreaker, LiveRuntime
from live.mt5_account import validate_account_mode
from live.mt5_executor import MT5LiveExecutor
from live.runner import ForexLiveOrchestrator
from live.runtime_controls import KillSwitch, RuntimeSafetyConfig

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ariatrading guarded MT5 runtime")
    parser.add_argument("--symbols", default="EURUSD,GBPUSD,USDJPY")
    parser.add_argument("--mode", choices=("DEMO", "LIVE"), default="DEMO")
    parser.add_argument("--timeframe", choices=("1m", "5m", "15m", "30m", "1h", "4h", "1D"), default="15m")
    parser.add_argument("--risk", type=float, default=0.01)
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--max-spread-points", type=float, default=30.0)
    parser.add_argument("--max-tick-age", type=float, default=10.0)
    parser.add_argument("--max-daily-drawdown", type=float, default=0.02)
    parser.add_argument("--max-positions", type=int, default=5)
    parser.add_argument("--max-positions-per-symbol", type=int, default=1)
    parser.add_argument("--max-clock-skew", type=float, default=5.0)
    parser.add_argument("--journal", default=str(PROJECT_ROOT / "data" / "execution_journal.json"))
    parser.add_argument("--circuit-state", default=str(PROJECT_ROOT / "data" / "daily_circuit_breaker.json"))
    parser.add_argument("--kill-switch", default=str(PROJECT_ROOT / "data" / "KILL_SWITCH"))
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    symbols = tuple(s.strip().upper() for s in args.symbols.split(",") if s.strip())
    limits = RuntimeSafetyConfig(
        max_tick_age_seconds=args.max_tick_age,
        max_spread_points=args.max_spread_points,
        max_daily_drawdown_fraction=args.max_daily_drawdown,
        max_positions=args.max_positions,
        max_positions_per_symbol=args.max_positions_per_symbol,
        max_clock_skew_seconds=args.max_clock_skew,
    )

    executor = MT5LiveExecutor()
    feed = None
    try:
        executor.connect()
        ok, reason = validate_account_mode(executor.mt5, args.mode)
        if not ok:
            raise RuntimeError(reason)

        journal = ExecutionJournal(args.journal)
        feed = MT5BarFeed()
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
            limits=limits,
            circuit_breaker=DailyCircuitBreaker(args.circuit_state, limits.max_daily_drawdown_fraction),
            kill_switch=KillSwitch(args.kill_switch),
        )
        runtime.run_forever(args.interval)
    finally:
        if executor:
            executor.disconnect()
        if feed is not None:
            feed.close()


if __name__ == "__main__":
    main()
