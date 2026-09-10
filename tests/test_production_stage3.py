import pytest

from live.production_stage3 import ProductionStage3Policy


class Account:
    login = 123456
    server = "Broker-Live"


def make_env(monkeypatch):
    values = {
        "ARIATRADING_ENABLE_LIVE": "I_UNDERSTAND_REAL_ORDERS",
        "ARIATRADING_LIVE_STAGE": "3",
        "ARIATRADING_LIVE_ACCOUNT": "123456",
        "ARIATRADING_LIVE_SERVER": "Broker-Live",
        "ARIATRADING_LIVE_SYMBOLS": "EURUSD,GBPUSD",
        "ARIATRADING_LIVE_MAX_RISK": "0.005",
        "ARIATRADING_LIVE_MAX_DAILY_DD": "0.02",
        "ARIATRADING_LIVE_MAX_SPREAD_POINTS": "30",
        "ARIATRADING_LIVE_MAX_TICK_AGE_SECONDS": "10",
        "ARIATRADING_LIVE_KILL_SWITCH": "OFF",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def test_stage3_loads_with_explicit_arm(monkeypatch):
    make_env(monkeypatch)
    policy = ProductionStage3Policy.from_env()
    assert policy.stage == 3
    assert policy.allowed_symbols == ("EURUSD", "GBPUSD")
    assert policy.max_open_positions == 2
    assert policy.max_orders_per_hour == 4


def test_stage3_defaults_to_kill_switch_on(monkeypatch):
    make_env(monkeypatch)
    monkeypatch.delenv("ARIATRADING_LIVE_KILL_SWITCH")
    with pytest.raises(RuntimeError, match="kill switch"):
        ProductionStage3Policy.from_env()


def test_stage3_rejects_nonfinite_risk(monkeypatch):
    make_env(monkeypatch)
    monkeypatch.setenv("ARIATRADING_LIVE_MAX_RISK", "nan")
    with pytest.raises(RuntimeError, match="finite"):
        ProductionStage3Policy.from_env()


def test_stage3_rejects_account_mismatch(monkeypatch):
    make_env(monkeypatch)
    policy = ProductionStage3Policy.from_env()
    Account.login = 999999
    try:
        with pytest.raises(RuntimeError, match="identity mismatch"):
            policy.validate_account_identity(Account())
    finally:
        Account.login = 123456


def test_stage3_requires_operational_guards(monkeypatch):
    make_env(monkeypatch)
    policy = ProductionStage3Policy.from_env()
    with pytest.raises(RuntimeError, match="stale"):
        policy.validate_operational_state(
            heartbeat_age_seconds=16,
            open_positions=0,
            orders_last_hour=0,
            reconciled=True,
            startup_self_test_passed=True,
        )
    with pytest.raises(RuntimeError, match="reconciliation"):
        policy.validate_operational_state(
            heartbeat_age_seconds=1,
            open_positions=0,
            orders_last_hour=0,
            reconciled=False,
            startup_self_test_passed=True,
        )


def test_stage3_rejects_limit_bypass(monkeypatch):
    make_env(monkeypatch)
    policy = ProductionStage3Policy.from_env()
    with pytest.raises(RuntimeError):
        policy.validate_market_state(spread_points=31, tick_age_seconds=1)
    with pytest.raises(RuntimeError):
        policy.validate_operational_state(
            heartbeat_age_seconds=1,
            open_positions=3,
            orders_last_hour=0,
            reconciled=True,
            startup_self_test_passed=True,
        )
    with pytest.raises(RuntimeError):
        policy.validate_order_risk(risk_per_trade=0.0051, daily_drawdown=0)
