from datetime import datetime, timedelta, timezone

import pytest

from bodyguard import Bodyguard, BodyguardConfig, SafetyRequest

NOW = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)


def make_request(**overrides):
    values = {
        "mode": "DEMO",
        "symbol": "EURUSD",
        "direction": "LONG",
        "entry": 1.1000,
        "stop_loss": 1.0950,
        "lot_size": 0.10,
        "signal_time": NOW - timedelta(seconds=30),
        "take_profit": 1.1075,
    }
    values.update(overrides)
    return SafetyRequest(**values)


def test_kill_switch_has_priority():
    decision = Bodyguard(BodyguardConfig(halted=True)).check(make_request(), now=NOW)
    assert decision.allowed is False
    assert decision.reason == "Bodyguard kill switch is active"


def test_valid_short_with_take_profit_is_allowed():
    decision = Bodyguard().check(
        make_request(direction="SHORT", entry=1.1000, stop_loss=1.1050, take_profit=1.0925),
        now=NOW,
    )
    assert decision.allowed is True


@pytest.mark.parametrize(
    "direction,take_profit",
    [("LONG", 1.1000), ("LONG", 1.0990), ("SHORT", 1.1000), ("SHORT", 1.1010)],
)
def test_take_profit_must_be_on_profit_side(direction, take_profit):
    entry = 1.1000
    stop = 1.0950 if direction == "LONG" else 1.1050
    decision = Bodyguard().check(
        make_request(direction=direction, entry=entry, stop_loss=stop, take_profit=take_profit),
        now=NOW,
    )
    assert decision.allowed is False


def test_none_take_profit_remains_supported():
    decision = Bodyguard().check(make_request(take_profit=None), now=NOW)
    assert decision.allowed is True


def test_infinite_take_profit_is_rejected():
    decision = Bodyguard().check(make_request(take_profit=float("inf")), now=NOW)
    assert decision.allowed is False


def test_exact_signal_age_limit_is_allowed():
    decision = Bodyguard().check(
        make_request(signal_time=NOW - timedelta(minutes=5)), now=NOW
    )
    assert decision.allowed is True


def test_allowlist_is_case_and_whitespace_normalized():
    guard = Bodyguard(BodyguardConfig(allowed_symbols=frozenset({" eurusd ", " GBPUSD"})))
    decision = guard.check(make_request(symbol=" EURUSD "), now=NOW)
    assert decision.allowed is True
