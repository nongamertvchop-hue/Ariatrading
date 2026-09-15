"""Run Ariatrading against an MT5 DEMO account.

This is the broker-execution entrypoint for development/staging. It uses the
same strategy, Forex risk engine, execution journal, and MT5 executor as the
production runtime, but hard-codes DEMO mode so this command cannot be used to
select a real-money execution mode.

Usage:
    python scripts/run_demo_bot.py --symbols EURUSD,GBPUSD --timeframe 15m

Required environment variables when the terminal is not already logged in:
    MT5_TERMINAL_PATH
    MT5_LOGIN
    MT5_PASSWORD
    MT5_SERVER

The MT5 Python package must be installed in the environment where this runs.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from adapters.mt5_feed import MT5BarFeed
from live.control_plane import BotControlPlane
from live.execution_guard import ExecutionJournal
from live.live_runtime import DailyCircuitBreaker, LiveRuntime, RuntimeLimits
from live.mt5_account import validate_account_mode
from live.mt5_executor import MT5LiveExecutor
from live.runner import ForexLiveOrchestrator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG = logging.getLogger("ariatrading.demo")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ariatrading MT5 DEMO trading bot")
    parser.add_argument(
        "--symbols",
        default="EURUSD",
    )
    parser.add_argument(
        "--timeframe",
        choices=["1m", "5m", "15m", "30m", "1h", "4h", "1D"],
        default="15m",
    )
    parser.add_argument("--risk", type=float, default=0.0025)
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--terminal-path", default=None)
    return parser


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    args = build_parser().parse_args()
    symbols = [value.strip().upper() for value in args.symbols.split(",") if value.strip()]
    if not symbols:
        raise SystemExit("--symbols must contain at least one symbol")
    if not 0 < args.risk <= 0.01:
        raise SystemExit("--risk must be > 0 and <= 0.01 for the demo runtime")
    if args.interval < 1:
        raise SystemExit("--interval must be >= 1 second")

    executor = MT5LiveExecutor(terminal_path=args.terminal_path)
    feed = None
    try:
        executor.connect()
        ok, reason = validate_account_mode(executor.mt5, "DEMO")
        if not ok:
            raise RuntimeError(f"MT5 DEMO account verification failed: {reason}")

        identity = executor.get_account_identity()
        executor.bind_account_identity(identity)
        LOG.info(
            "bound MT5 DEMO account login=%s server=%s company=%s",
            identity.login,
            identity.server,
            identity.company,
        )

        # Reuse the already-connected MT5 session. Creating a second MT5
        # connection here can invalidate the executor's terminal session.
        feed = MT5BarFeed(mt5_module=executor.mt5, manage_connection=False)
        journal = ExecutionJournal(PROJECT_ROOT / "data" / "execution_journal.json")
        orchestrator = ForexLiveOrchestrator(
            symbols=symbols,
            mode="DEMO",
            timeframe=args.timeframe,
            risk_per_trade=args.risk,
            feed=feed,
            executor=executor,
            execution_journal=journal,
        )
        control = BotControlPlane(PROJECT_ROOT / "data" / "bot_control.json")
        runtime = LiveRuntime(
            orchestrator=orchestrator,
            feed=feed,
            executor=executor,
            journal=journal,
            control=control,
            limits=RuntimeLimits(
                max_tick_age_seconds=5,
                max_spread_points=30,
                max_daily_drawdown_fraction=0.01,
            ),
            circuit_breaker=DailyCircuitBreaker(
                PROJECT_ROOT / "data" / "daily_circuit_breaker.json",
                max_drawdown_fraction=0.01,
            ),
        )
        LOG.info(
            "Ariatrading MT5 DEMO bot ready: symbols=%s timeframe=%s risk=%.4f interval=%.1fs",
            ",".join(symbols),
            args.timeframe,
            args.risk,
            args.interval,
        )
        LOG.info("Default control state is STOP; use scripts/bot_control.py start to run")
        runtime.run_forever(args.interval)
    finally:
        if feed is not None:
            feed.close()
        executor.disconnect()


if __name__ == "__main__":
    main()
