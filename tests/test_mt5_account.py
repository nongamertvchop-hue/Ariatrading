from types import SimpleNamespace

from live.mt5_account import validate_account_mode


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_REAL = 2

    def __init__(self, trade_mode, trade_allowed=True, trade_expert=True, login=12345, server="Broker-Real"):
        self._info = SimpleNamespace(
            trade_mode=trade_mode,
            trade_allowed=trade_allowed,
            trade_expert=trade_expert,
            login=login,
            server=server,
        )

    def account_info(self):
        return self._info

    def last_error(self):
        return (500, "account unavailable")


def _arm_live(monkeypatch, stage="1", login="12345", server="Broker-Real", symbols="EURUSD"):
    monkeypatch.setenv("ARIATRADING_ENABLE_LIVE", "I_UNDERSTAND_REAL_ORDERS")
    monkeypatch.setenv("ARIATRADING_LIVE_STAGE", stage)
    monkeypatch.setenv("ARIATRADING_LIVE_ACCOUNT", login)
    monkeypatch.setenv("ARIATRADING_LIVE_SERVER", server)
    monkeypatch.setenv("ARIATRADING_LIVE_SYMBOLS", symbols)


def test_live_is_disabled_without_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("ARIATRADING_ENABLE_LIVE", raising=False)
    ok, reason = validate_account_mode(FakeMT5(2), "LIVE")
    assert not ok
    assert "LIVE execution is disabled by default" in reason


def test_live_requires_real_account(monkeypatch):
    _arm_live(monkeypatch)
    ok, reason = validate_account_mode(FakeMT5(0), "LIVE")
    assert not ok
    assert "requested LIVE" in reason
    assert "DEMO" in reason


def test_demo_requires_demo_account():
    ok, reason = validate_account_mode(FakeMT5(2), "DEMO")
    assert not ok
    assert "requested DEMO" in reason
    assert "REAL" in reason


def test_matching_live_account_is_allowed(monkeypatch):
    _arm_live(monkeypatch)
    ok, reason = validate_account_mode(FakeMT5(2), "LIVE")
    assert ok
    assert reason == "account mode verified: LIVE"


def test_matching_stage2_live_account_is_allowed(monkeypatch):
    _arm_live(monkeypatch, stage="2", login="22334455", symbols="EURUSD,GBPUSD")
    ok, reason = validate_account_mode(FakeMT5(2, login=22334455, server="Broker-Real"), "LIVE")
    assert ok
    assert reason == "account mode verified: LIVE"


def test_stage2_rejects_wrong_account(monkeypatch):
    _arm_live(monkeypatch, stage="2", login="22334455", symbols="EURUSD,GBPUSD")
    ok, reason = validate_account_mode(FakeMT5(2, login=12345), "LIVE")
    assert not ok
    assert "Stage 2 account identity mismatch" in reason


def test_matching_demo_account_is_allowed():
    ok, reason = validate_account_mode(FakeMT5(0), "DEMO")
    assert ok
    assert reason == "account mode verified: DEMO"


def test_live_rejects_wrong_account(monkeypatch):
    _arm_live(monkeypatch)
    ok, reason = validate_account_mode(FakeMT5(2, login=12346), "LIVE")
    assert not ok
    assert "account identity mismatch" in reason


def test_live_rejects_wrong_server(monkeypatch):
    _arm_live(monkeypatch)
    ok, reason = validate_account_mode(FakeMT5(2, server="Broker-Demo"), "LIVE")
    assert not ok
    assert "account identity mismatch" in reason


def test_execution_disabled_for_account_is_rejected(monkeypatch):
    _arm_live(monkeypatch)
    ok, reason = validate_account_mode(FakeMT5(2, trade_allowed=False), "LIVE")
    assert not ok
    assert reason == "MT5 account does not allow trading"


def test_ea_trading_disabled_is_rejected(monkeypatch):
    _arm_live(monkeypatch)
    ok, reason = validate_account_mode(FakeMT5(2, trade_expert=False), "LIVE")
    assert not ok
    assert reason == "MT5 Expert Advisor trading is disabled for this account"


def test_account_info_failure_is_rejected(monkeypatch):
    _arm_live(monkeypatch)

    class BrokenMT5(FakeMT5):
        def account_info(self):
            return None

    ok, reason = validate_account_mode(BrokenMT5(2), "LIVE")
    assert not ok
    assert "account_info unavailable" in reason


def test_alert_only_does_not_require_account_mode():
    ok, reason = validate_account_mode(FakeMT5(0), "ALERT_ONLY")
    assert ok
    assert "not applicable" in reason
