import argparse
from types import SimpleNamespace

import pytest

from live.live_runtime_cli import (
    _resolve_mt5_connection_config,
    _validate_connected_live_account,
    _validate_live_startup,
    build_parser,
)
from live.production_stage1 import ProductionStage1Policy


def test_hardened_runtime_cli_is_demo_by_default():
    args = build_parser().parse_args([])
    assert args.mode == "DEMO"
    assert args.symbols == "EURUSD"
    assert args.timeframe == "15m"
    assert args.risk == 0.0025
    assert args.interval == 5.0
    assert args.max_tick_age == 5.0
    assert args.max_spread_points == 20.0
    assert args.max_daily_drawdown == 0.01


def test_hardened_runtime_cli_exposes_only_execution_modes():
    action = next(item for item in build_parser()._actions if item.dest == "mode")
    assert action.choices == ["DEMO", "LIVE"]


def test_hardened_runtime_cli_accepts_operational_limits():
    args = build_parser().parse_args([
        "--mode", "DEMO",
        "--symbols", "EURUSD,GBPUSD",
        "--timeframe", "1m",
        "--risk", "0.002",
        "--interval", "2.5",
        "--max-tick-age", "4",
        "--max-spread-points", "18",
        "--max-daily-drawdown", "0.008",
    ])
    assert args.mode == "DEMO"
    assert args.symbols == "EURUSD,GBPUSD"
    assert args.timeframe == "1m"
    assert args.risk == 0.002
    assert args.interval == 2.5
    assert args.max_tick_age == 4.0
    assert args.max_spread_points == 18.0
    assert args.max_daily_drawdown == 0.008


def test_hardened_runtime_cli_rejects_non_positive_interval():
    parser = build_parser()
    try:
        parser.parse_args(["--interval", "0"])
    except SystemExit as exc:
        assert exc.code != 0
    else:
        raise AssertionError("CLI must reject a non-positive runtime interval")


def _runtime_args(mode="LIVE", risk=0.0025, dd=0.01, spread=20.0, tick_age=5.0):
    return argparse.Namespace(
        mode=mode,
        risk=risk,
        max_daily_drawdown=dd,
        max_spread_points=spread,
        max_tick_age=tick_age,
    )


def _arm_live(monkeypatch):
    monkeypatch.setenv("ARIATRADING_ENABLE_LIVE", "I_UNDERSTAND_REAL_ORDERS")
    monkeypatch.setenv("ARIATRADING_LIVE_STAGE", "1")
    monkeypatch.setenv("ARIATRADING_LIVE_ACCOUNT", "12345")
    monkeypatch.setenv("ARIATRADING_LIVE_SERVER", "Broker-Real")
    monkeypatch.setenv("ARIATRADING_LIVE_SYMBOLS", "EURUSD")


def test_direct_live_cli_is_fail_closed_without_stage1(monkeypatch):
    monkeypatch.delenv("ARIATRADING_LIVE_STAGE", raising=False)
    monkeypatch.delenv("ARIATRADING_ENABLE_LIVE", raising=False)
    with pytest.raises(RuntimeError, match="LIVE production stage is not armed"):
        _validate_live_startup(_runtime_args(), ["EURUSD"])


def test_direct_live_cli_enforces_symbol_and_limits(monkeypatch):
    _arm_live(monkeypatch)
    with pytest.raises(RuntimeError, match="symbol allowlist mismatch"):
        _validate_live_startup(_runtime_args(), ["GBPUSD"])
    with pytest.raises(RuntimeError, match="risk exceeds policy"):
        _validate_live_startup(_runtime_args(risk=0.005), ["EURUSD"])


def test_demo_cli_does_not_require_live_arm(monkeypatch):
    monkeypatch.delenv("ARIATRADING_LIVE_STAGE", raising=False)
    monkeypatch.delenv("ARIATRADING_ENABLE_LIVE", raising=False)
    _validate_live_startup(_runtime_args(mode="DEMO"), ["EURUSD"])


def test_live_connection_defaults_to_stage1_account(monkeypatch):
    _arm_live(monkeypatch)
    monkeypatch.delenv("MT5_LOGIN", raising=False)
    monkeypatch.delenv("MT5_SERVER", raising=False)
    policy = ProductionStage1Policy.from_env()
    assert _resolve_mt5_connection_config("LIVE", policy) == (12345, "", "Broker-Real")


def test_live_connected_account_must_match_stage1_identity(monkeypatch):
    _arm_live(monkeypatch)
    policy = ProductionStage1Policy.from_env()

    class FakeExecutor:
        mt5 = SimpleNamespace(
            account_info=lambda: SimpleNamespace(
                login=99999,
                server="Broker-Real",
            )
        )

    with pytest.raises(RuntimeError, match="account identity mismatch"):
        _validate_connected_live_account(FakeExecutor(), policy)


def test_live_connected_account_accepts_exact_stage1_identity(monkeypatch):
    _arm_live(monkeypatch)
    policy = ProductionStage1Policy.from_env()

    class FakeExecutor:
        mt5 = SimpleNamespace(
            account_info=lambda: SimpleNamespace(
                login=12345,
                server="Broker-Real",
            )
        )

    _validate_connected_live_account(FakeExecutor(), policy)
