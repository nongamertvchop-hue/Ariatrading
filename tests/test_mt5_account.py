from types import SimpleNamespace

from live.mt5_account import validate_account_mode


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_REAL = 2

    def __init__(self, trade_mode, trade_allowed=True, trade_expert=True):
        self._info = SimpleNamespace(
            trade_mode=trade_mode,
            trade_allowed=trade_allowed,
            trade_expert=trade_expert,
        )

    def account_info(self):
        return self._info

    def last_error(self):
        return (500, "account unavailable")


def test_live_requires_real_account():
    ok, reason = validate_account_mode(FakeMT5(0), "LIVE")
    assert not ok
    assert "requested LIVE" in reason
    assert "DEMO" in reason


def test_demo_requires_demo_account():
    ok, reason = validate_account_mode(FakeMT5(2), "DEMO")
    assert not ok
    assert "requested DEMO" in reason
    assert "REAL" in reason


def test_matching_live_account_is_allowed():
    ok, reason = validate_account_mode(FakeMT5(2), "LIVE")
    assert ok
    assert reason == "account mode verified: LIVE"


def test_matching_demo_account_is_allowed():
    ok, reason = validate_account_mode(FakeMT5(0), "DEMO")
    assert ok
    assert reason == "account mode verified: DEMO"


def test_execution_disabled_for_account_is_rejected():
    ok, reason = validate_account_mode(FakeMT5(2, trade_allowed=False), "LIVE")
    assert not ok
    assert reason == "MT5 account does not allow trading"


def test_ea_trading_disabled_is_rejected():
    ok, reason = validate_account_mode(FakeMT5(2, trade_expert=False), "LIVE")
    assert not ok
    assert reason == "MT5 Expert Advisor trading is disabled for this account"


def test_account_info_failure_is_rejected():
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
