from datetime import datetime, timedelta, timezone

import pytest

from bodyguard import Bodyguard, BodyguardConfig, SafetyRequest

NOW = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)


def request(**overrides):
    values = {
        "mode": "DEMO",
        "symbol": "EURUSD",
        "direction": "LONG",
        "entry": 1.1000,
        "stop_loss": 1.0950,
        "lot_size": 0.10,
        "signal_time": NOW - timedelta(seconds=30),
    }
    values.update(overrides)
    return SafetyRequest(**values)


def test_allows_valid_demo_long_request():
    decision = Bodyguard().check(request(), now=NOW)
    assert decision.allowed is True


def test_rejects_live_mode():
    decision = Bodyguard().check(request(mode="LIVE"), now=NOW)
    assert decision.allowed is False


def test_rejects_invalid_stop_for_long():
    decision = Bodyguard().check(request(stop_loss=1.1001), now=NOW)
    assert decision.allowed is False


def test_rejects_invalid_stop_for_short():
    decision = Bodyguard().check(
        request(direction="SHORT", entry=1.1000, stop_loss=1.0950), now=NOW
    )
    assert decision.allowed is False


def test_rejects_stale_signal():
    decision = Bodyguard().check(
        request(signal_time=NOW - timedelta(minutes=5, seconds=1)), now=NOW
    )
    assert decision.allowed is False


def test_rejects_future_signal():
    decision = Bodyguard().check(
        request(signal_time=NOW + timedelta(seconds=1)), now=NOW
    )
    assert decision.allowed is False


def test_rejects_naive_signal_time():
    decision = Bodyguard().check(
        request(signal_time=datetime(2026, 9, 10, 7, 59, 30)), now=NOW
    )
    assert decision.allowed is False


def test_rejects_lot_above_hard_limit():
    guard = Bodyguard(BodyguardConfig(max_lot_size=0.50))
    decision = guard.check(request(lot_size=0.51), now=NOW)
    assert decision.allowed is False


def test_rejects_non_allowlisted_symbol():
    guard = Bodyguard(BodyguardConfig(allowed_symbols=frozenset({"EURUSD"})))
    decision = guard.check(request(symbol="GBPUSD"), now=NOW)
    assert decision.allowed is False


def test_normalizes_allowlist_and_request_text():
    guard = Bodyguard(BodyguardConfig(allowed_symbols=frozenset({" eurusd "})))
    decision = guard.check(
        request(mode=" demo ", symbol=" eurusd ", direction=" long "), now=NOW
    )
    assert decision.allowed is True


@pytest.mark.parametrize("field", ["entry", "stop_loss", "lot_size"])
def test_rejects_non_finite_numbers(field):
    decision = Bodyguard().check(request(**{field: float("nan")}), now=NOW)
    assert decision.allowed is False
