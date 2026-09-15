"""CLI entry point for the hardened continuous MT5 runtime."""

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
from live.runtime_status import RuntimeStatusStore

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
    parser.add_argument("--status-path", default=os.getenv("BOT_STATUS_PATH", "data/bot_status.json"), help="Atomic runtime heartbeat/status snapshot")
    return parser


def _effective_login(args: argparse.Namespace) -> int | None:
    if args.login is not None:
        return args.login
    raw = os.getenv("MT5_LOGIN", "").strip()
    return int(raw) if raw else None


def _validate_live_startup(args: argparse.Namespace, symbols: list[str]) -> None:
    """Apply the production policy even when this CLI is invoked directly."""
    if args.mode != "LIVE":
        return
    policy = ProductionStage1Policy.from_env()
    policy.validate_symbols(symbols)
    policy.validate_runtime_limits(risk_per_trade=args.risk, max_daily_drawdown=args.max_daily_drawdown, max_spread_points=args.max_spread_points, max_tick_age_seconds=args.max_tick_age)
    login = _effective_login(args)
    if login is not None and login != policy.account_login:
        raise RuntimeError("MT5 login does not match LIVE Stage-1 account policy")
    if args.server and args.server != policy.server:
        raise RuntimeError("MT5 server does not match LIVE Stage-1 server policy")


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

    executor = MT5LiveExecutor(terminal_path=args.terminal_path or None, magic_number=args.magic_number, login=login, password=args.password, server=args.server)
    feed = None
    journal = ExecutionJournal("data/execution_journal.json")
    circuit_breaker = DailyCircuitBreaker("data/daily_circuit_breaker.json", max_drawdown_fraction=args.max_daily_drawdown)
    control = BotControlPlane(args.control_path)
    status = RuntimeStatusStore(args.status_path)

    try:
        executor.connect()
        feed = MT5BarFeed(mt5_module=executor.mt5, manage_connection=False)
        orchestrator = ForexLiveOrchestrator(symbols=symbols, mode=args.mode, timeframe=args.timeframe, risk_per_trade=args.risk, feed=feed, executor=executor, execution_journal=journal)
        runtime = LiveRuntime(
            orchestrator=orchestrator,
            feed=feed,
            executor=executor,
            journal=journal,
            limits=RuntimeLimits(max_tick_age_seconds=args.max_tick_age, max_spread_points=args.max_spread_points, max_daily_drawdown_fraction=args.max_daily_drawdown),
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
