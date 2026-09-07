import pytest

from strategy.timeframe import (
    SUPPORTED_TIMEFRAMES,
    adaptive_confirmation_buffer,
    adaptive_zone_tolerance,
    get_timeframe_config,
)


def candles():
    return [
        {"open": 1.1000, "high": 1.1010, "low": 1.0990, "close": 1.1005},
        {"open": 1.1005, "high": 1.1020, "low": 1.1000, "close": 1.1015},
        {"open": 1.1015, "high": 1.1030, "low": 1.1005, "close": 1.1020},
    ]


def test_all_supported_timeframes_have_config():
    assert list(SUPPORTED_TIMEFRAMES) == ["1m", "5m", "15m", "30m", "1h", "4h", "1D"]
    for timeframe in SUPPORTED_TIMEFRAMES:
        config = get_timeframe_config(timeframe)
        assert config.name == timeframe


def test_adaptive_distances_are_positive():
    data = candles()
    for timeframe in SUPPORTED_TIMEFRAMES:
        assert adaptive_zone_tolerance(data, timeframe) > 0
        assert adaptive_confirmation_buffer(data, timeframe) > 0


def test_15m_zone_tolerance_remains_tighter_than_30m():
    data = candles()
    tolerance_15m = adaptive_zone_tolerance(data, "15m")
    tolerance_30m = adaptive_zone_tolerance(data, "30m")

    # 15m was deliberately calibrated tighter to avoid swallowing normal
    # reaction candles into the zone. Keep this invariant explicit so a later
    # timeframe refactor cannot silently widen it again.
    assert tolerance_15m < tolerance_30m


def test_unknown_timeframe_is_rejected():
    with pytest.raises(ValueError):
        get_timeframe_config("2m")
