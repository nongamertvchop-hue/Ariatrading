"""CLI entry point for the hardened continuous MT5 runtime.

This module intentionally keeps ALERT_ONLY out of the execution runtime. Use
DEMO for broker-demo execution and LIVE only after the Stage-1 deployment gate
has been explicitly armed. The persistent control plane defaults to STOP, so
starting the process never implies permission to place an order.
"""

from __future__ import annotations

import argparse
import logging
import math
import os

from adapters.mt5_feed import MT5BarFeed
from live.control_plane import BotControlPlane
from live.execution_guard import ExecutionJournal
from live.live_runtime import DailyCircuitBreaker, LiveRuntime, RuntimeLimits
from live.mt5_executor import MT5LiveExecutor
from live.production_stage1 import ProductionStage1Policy
from live.runner import ForexLiveOrchestrator

logger = logging.getLogger("ariatrading.live_runtime_cli")


def _positive_float(value: str) -> float:
    """Parse a finite positive float so invalid runtime limits fail at startup."""
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be a finite value greater than 0")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ariatrading hardened MT5 trading runtime")
    parser.add_argument("--symbols", default="EURUSD", help="Comma-separated broker symbols")
    parser.add_argument("--mode", choices=["DEMO", "LIVE"], default="DEMO")
    parser.add_argument("--timeframe", default="15m", help="Candle timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1D)")
    parser.add_argument("--risk", type=_positive_float, default=0.0025, help="Risk fraction per trade")
    parser.add_argument("--interval", type=_positive_float, default=5.0, help="Runtime cycle interval in seconds")
    parser.add_argument("--max-tick-age", type=_positive_float, default=5.0, help="Maximum accepted broker tick age")
    parser.add_argument("--max-spread-points", type=_positive_float, default=20.0, help="Maximum accepted spread in points")
    parser.add_argument("--max-daily-drawdown", type=_positive_float, default=0.01, help="Daily equity drawdown circuit-breaker fraction")
    parser.add_argument("--terminal-path", default=os.getenv("MT5_TERMINAL_PATH", ""), help="Optional MT5 terminal executable path")
    parser.add_argument("--login", type=int, default=None, help="Optional explicit MT5 account login (or MT5_LOGIN env)")
    parser.add_argument("--password", default=os.getenv("MT5_PASSWORD", ""), help="Optional MT5 account password; prefer MT5_PASSWORD environment variable")
    parser.add_argument("--server", default=os.getenv("MT5_SERVER", ""), help="Optional explicit MT5 trade server")
    parser.add_argument("--magic-number", type=int, default=int(os.getenv("MT5_MAGIC_NUMBER", "8808")), help="Strategy magic number used for position ownership")
    parser.add_argument("--control-path", default=os.getenv("BOT_CONTROL_PATH", "data/bot_control.json"), help="Persistent RUN/PAUSE/STOP control state")
    return parser


def _effective_login(args: argparse.Namespace) -> int | None:
    if args.login is not None:
        return args.login
    raw = os.getenv("MT5_LOGIN", "").strip()
    return int(raw) if raw else None


def _validate_live_startup(args: argparse.Namespace, symbols: list[str]) -> None:
    """Apply the production policy before establishing a LIVE session."""
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
    login = _effective_login(args)
    if login is not None and login != policy.account_login:
        raise RuntimeError("MT5 login does not match LIVE Stage-1 account policy")
    if args.server and args.server != policy.server:
        raise RuntimeError("MT5 server does not match LIVE Stage-1 server policy")


def _resolve_stage1_connection_config(
    args: argparse.Namespace, policy: ProductionStage1Policy | None
) -> tuple[int | None, str, str]:
    """Return the effective MT5 login/password/server without logging the password."""
    login = _effective_login(args)
    server = args.server.strip()
    password = args.password
    if policy is not None:
        login = policy.account_login if login is None else login
        server = policy.server if not server else server
    return login, password, server


def _validate_connected_live_account(executor: MT5LiveExecutor, policy: ProductionStage1Policy) -> None:
    """Reject a connected account unless it exactly matches the Stage-1 allowlist."""
    if executor.mt5 is None:
        raise RuntimeError("MT5 module unavailable")
    account_info = executor.mt5.account_info()
    policy.validate_account_identity(account_info)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = build_parser().parse_args(argv)
    symbols = [value.strip().upper() for value in args.symbols.split(",") if value.strip()]
    if not symbols:
        raise SystemExit("--symbols must contain at least one symbol")
    if args.magic_number <= 0:
        raise SystemExit("--magic-number must be positive")

    login = _effective_login(args)
    if login is not None and login <= 0:
        raise SystemExit("MT5_LOGIN/--login must be positive")

    try:
        _validate_live_startup(args, symbols)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    policy = ProductionStage1Policy.from_env() if args.mode == "LIVE" else None
    login, password, server = _resolve_stage1_connection_config(args, policy)
    executor = MT5LiveExecutor(
        terminal_path=args.terminal_path or None,
        magic_number=args.magic_number,
        login=login,
        password=password,
        server=server,
    )
    feed = None
    journal = ExecutionJournal("data/execution_journal.json")
    circuit_breaker = DailyCircuitBreaker(
        "data/daily_circuit_breaker.json",
        max_drawdown_fraction=args.max_daily_drawdown,
    )
    control = BotControlPlane(args.control_path)

    try:
        # One MT5 connection is the source of truth for both market data and
        # execution. A second initialize()/shutdown() pair can race the same
        # terminal session and makes account state harder to reason about.
        executor.connect()
        if policy is not None:
            _validate_connected_live_account(executor, policy)
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
        )
        logger.info("Starting hardened Ariatrading runtime: mode=%s symbols=%s control=%s", args.mode, symbols, control.read().state)
        runtime.run_forever(args.interval)
    finally:
        if feed is not None:
            feed.close()
        executor.disconnect()


if __name__ == "__main__":
    main()
