import pytest

from live.production_stage2 import ProductionStage2Policy


def _arm(monkeypatch, symbols="EURUSD,GBPUSD"):
    monkeypatch.setenv("ARIATRADING_ENABLE_LIVE", "I_UNDERSTAND_REAL_ORDERS")
    monkeypatch.setenv("ARIATRADING_LIVE_STAGE", "2")
    monkeypatch.setenv("ARIATRADING_LIVE_ACCOUNT", "22334455")
    monkeypatch.setenv("ARIATRADING_LIVE_SERVER", "Broker-Real")
    monkeypatch.setenv("ARIATRADING_LIVE_SYMBOLS", symbols)


def test_stage2_requires_explicit_arm(monkeypatch):
    monkeypatch.delenv("ARIATRADING_LIVE_STAGE", raising=False)
    with pytest.raises(RuntimeError, match="stage is not armed"):
        ProductionStage2Policy.from_env()


def test_stage2_defaults_and_caps(monkeypatch):
    _arm(monkeypatch)
    policy = ProductionStage2Policy.from_env()
    assert policy.stage == 2
    assert policy.allowed_symbols == ("EURUSD", "GBPUSD")
    assert policy.max_risk_per_trade == 0.005
    assert policy.max_daily_drawdown == 0.02
    assert policy.max_spread_points == 30.0
    assert policy.max_tick_age_seconds == 10.0


def test_stage2_accepts_one_or_two_allowlisted_symbols(monkeypatch):
    _arm(monkeypatch)
    policy = ProductionStage2Policy.from_env()
    policy.validate_symbols(["EURUSD"])
    policy.validate_symbols(["EURUSD", "GBPUSD"])
    with pytest.raises(RuntimeError, match="symbol allowlist mismatch"):
        policy.validate_symbols(["USDJPY"])
    with pytest.raises(RuntimeError, match="symbol allowlist mismatch"):
        policy.validate_symbols(["EURUSD", "GBPUSD", "USDJPY"])


def test_stage2_rejects_values_above_policy(monkeypatch):
    _arm(monkeypatch)
    policy = ProductionStage2Policy.from_env()
    with pytest.raises(RuntimeError, match="risk exceeds policy"):
        policy.validate_runtime_limits(
            risk_per_trade=0.0051,
            max_daily_drawdown=0.02,
            max_spread_points=30,
            max_tick_age_seconds=10,
        )
    with pytest.raises(RuntimeError, match="drawdown limit exceeds policy"):
        policy.validate_runtime_limits(
            risk_per_trade=0.005,
            max_daily_drawdown=0.0201,
            max_spread_points=30,
            max_tick_age_seconds=10,
        )


def test_stage2_rejects_non_finite_configuration(monkeypatch):
    _arm(monkeypatch)
    monkeypatch.setenv("ARIATRADING_LIVE_MAX_RISK", "nan")
    with pytest.raises(RuntimeError, match="finite number"):
        ProductionStage2Policy.from_env()
