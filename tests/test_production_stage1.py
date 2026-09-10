from types import SimpleNamespace

import pytest

from live.production_stage1 import ProductionStage1Policy


class _Account:
    def __init__(self, login=12345, server="Broker-Real"):
        self.login = login
        self.server = server


def _arm(monkeypatch):
    monkeypatch.setenv("ARIATRADING_ENABLE_LIVE", "I_UNDERSTAND_REAL_ORDERS")
    monkeypatch.setenv("ARIATRADING_LIVE_STAGE", "1")
    monkeypatch.setenv("ARIATRADING_LIVE_ACCOUNT", "12345")
    monkeypatch.setenv("ARIATRADING_LIVE_SERVER", "Broker-Real")
    monkeypatch.setenv("ARIATRADING_LIVE_SYMBOLS", "EURUSD")


def test_stage1_is_fail_closed_by_default(monkeypatch):
    monkeypatch.delenv("ARIATRADING_LIVE_STAGE", raising=False)
    with pytest.raises(RuntimeError, match="LIVE production stage is not armed"):
        ProductionStage1Policy.from_env()


def test_stage1_requires_exact_account_and_server(monkeypatch):
    _arm(monkeypatch)
    policy = ProductionStage1Policy.from_env()

    policy.validate_account_identity(_Account())
    with pytest.raises(RuntimeError, match="account identity mismatch"):
        policy.validate_account_identity(_Account(login=12346))
    with pytest.raises(RuntimeError, match="account identity mismatch"):
        policy.validate_account_identity(_Account(server="Broker-Demo"))


def test_stage1_allows_exactly_one_configured_symbol(monkeypatch):
    _arm(monkeypatch)
    policy = ProductionStage1Policy.from_env()
    policy.validate_symbols(["EURUSD"])
    with pytest.raises(RuntimeError, match="symbol allowlist mismatch"):
        policy.validate_symbols(["GBPUSD"])
    with pytest.raises(RuntimeError, match="symbol allowlist mismatch"):
        policy.validate_symbols(["EURUSD", "GBPUSD"])


def test_stage1_hard_caps_risk_and_operational_limits(monkeypatch):
    _arm(monkeypatch)
    policy = ProductionStage1Policy.from_env()
    policy.validate_runtime_limits(
        risk_per_trade=0.0025,
        max_daily_drawdown=0.01,
        max_spread_points=20,
        max_tick_age_seconds=5,
    )

    with pytest.raises(RuntimeError, match="risk exceeds policy"):
        policy.validate_runtime_limits(
            risk_per_trade=0.0026,
            max_daily_drawdown=0.01,
            max_spread_points=20,
            max_tick_age_seconds=5,
        )


def test_stage1_rejects_policy_values_above_hard_cap(monkeypatch):
    _arm(monkeypatch)
    monkeypatch.setenv("ARIATRADING_LIVE_MAX_RISK", "0.01")
    with pytest.raises(RuntimeError, match="ARIATRADING_LIVE_MAX_RISK"):
        ProductionStage1Policy.from_env()
