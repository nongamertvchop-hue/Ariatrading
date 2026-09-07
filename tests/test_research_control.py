from datetime import datetime, timezone

import pytest

from strategy.research_control import (
    ResearchConfig,
    build_research_run,
    config_fingerprint,
    fingerprint_candles,
)


def make_candles():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        {
            "time": start,
            "open": 1.1000,
            "high": 1.1010,
            "low": 1.0990,
            "close": 1.1005,
        },
        {
            "time": start.replace(minute=1),
            "open": 1.1005,
            "high": 1.1015,
            "low": 1.0995,
            "close": 1.1010,
        },
    ]


def make_config():
    return ResearchConfig(
        symbol="EURUSD",
        timeframe="15m",
        history_bars=20,
        test_bars=10,
        step_bars=10,
    )


def test_fingerprint_is_stable_across_dict_order():
    first = make_candles()
    second = [
        {"close": row["close"], "low": row["low"], "time": row["time"], "high": row["high"], "open": row["open"]}
        for row in first
    ]
    assert fingerprint_candles(first).sha256 == fingerprint_candles(second).sha256


def test_fingerprint_changes_when_data_changes():
    candles = make_candles()
    original = fingerprint_candles(candles).sha256
    candles[1]["close"] = 1.0999
    assert fingerprint_candles(candles).sha256 != original


def test_naive_datetime_is_rejected():
    candles = make_candles()
    candles[0]["time"] = datetime(2026, 1, 1)
    with pytest.raises(ValueError, match="timezone-aware"):
        fingerprint_candles(candles)


def test_config_fingerprint_is_stable_and_changes_with_config():
    first = make_config()
    second = ResearchConfig(
        symbol="EURUSD",
        timeframe="15m",
        history_bars=20,
        test_bars=10,
        step_bars=10,
    )
    changed = ResearchConfig(
        symbol="GBPUSD",
        timeframe="15m",
        history_bars=20,
        test_bars=10,
        step_bars=10,
    )
    assert config_fingerprint(first) == config_fingerprint(second)
    assert config_fingerprint(first) != config_fingerprint(changed)


def test_build_research_run_binds_both_fingerprints():
    config = make_config()
    run = build_research_run(config, make_candles())
    assert run.config == config
    assert run.config_sha256 == config_fingerprint(config)
    assert run.dataset.candle_count == 2
    assert run.dataset.first_time == "2026-01-01T00:00:00+00:00"
    assert run.dataset.last_time == "2026-01-01T00:01:00+00:00"


def test_config_rejects_invalid_windows_and_parameters():
    with pytest.raises(ValueError):
        ResearchConfig("EURUSD", "15m", 0, 10, 10)
    with pytest.raises(ValueError):
        ResearchConfig("EURUSD", "15m", 20, 0, 1)
    with pytest.raises(ValueError):
        ResearchConfig("EURUSD", "15m", 20, 10, 5)
    with pytest.raises(ValueError):
        ResearchConfig("EURUSD", "15m", 20, 10, 10, reward_risk=0)
