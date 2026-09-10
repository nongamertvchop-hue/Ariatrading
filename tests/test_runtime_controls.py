from datetime import datetime, timedelta, timezone

import pytest

from live.runtime_controls import (
    KillSwitch,
    RuntimeSafetyConfig,
    check_clock_skew,
    exposure_counts,
    validate_runtime_configuration,
)


def test_runtime_config_rejects_invalid_limits():
    config = RuntimeSafetyConfig(max_daily_drawdown_fraction=1.0)
    with pytest.raises(ValueError):
        config.validate()


def test_runtime_config_normalizes_symbols():
    config = RuntimeSafetyConfig()
    symbols = validate_runtime_configuration(
        timeframe="15m", symbols=(" eurusd ", "EURUSD", "GBPUSD"), config=config
    )
    assert symbols == ("EURUSD", "GBPUSD")


def test_runtime_config_rejects_unknown_timeframe():
    with pytest.raises(ValueError, match="unsupported timeframe"):
        validate_runtime_configuration(
            timeframe="2m", symbols=("EURUSD",), config=RuntimeSafetyConfig()
        )


def test_clock_skew_gate():
    now = datetime(2026, 9, 10, 12, tzinfo=timezone.utc)
    assert check_clock_skew(now, now + timedelta(seconds=2), 5)[0]
    ok, reason = check_clock_skew(now, now + timedelta(seconds=6), 5)
    assert not ok
    assert "clock skew" in reason


def test_clock_skew_requires_timezone_aware_values():
    now = datetime(2026, 9, 10, 12, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        check_clock_skew(datetime(2026, 9, 10, 12), now, 5)


def test_exposure_counts():
    positions = [type("P", (), {"symbol": "EURUSD"})(), type("P", (), {"symbol": "EURUSD"})(), type("P", (), {"symbol": "GBPUSD"})()]
    total, per_symbol = exposure_counts(positions)
    assert total == 3
    assert per_symbol == {"EURUSD": 2, "GBPUSD": 1}


def test_kill_switch_is_durable(tmp_path):
    switch = KillSwitch(tmp_path / "KILL_SWITCH")
    assert switch.check()[0]
    switch.engage("operator emergency stop")
    ok, reason = switch.check()
    assert not ok
    assert "kill switch" in reason
    assert switch.engaged()
    switch.release()
    assert switch.check()[0]
