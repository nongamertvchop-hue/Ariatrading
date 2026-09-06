"""Timeframe-aware, indicator-free price-distance utilities.

The strategy rules stay identical from 1m through 1D. Only the size of a
price zone and breakout confirmation distance adapts to recent candle ranges.
No orders are placed here.
"""

from dataclasses import dataclass


SUPPORTED_TIMEFRAMES = ("1m", "5m", "15m", "30m", "1h", "4h", "1D")


@dataclass(frozen=True)
class TimeframeConfig:
    name: str
    lookback: int
    range_multiplier: float
    min_zone_distance: float
    max_zone_distance: float
    confirmation_multiplier: float


_CONFIGS = {
    "1m": TimeframeConfig("1m", 30, 0.80, 0.00005, 0.00100, 0.20),
    "5m": TimeframeConfig("5m", 30, 0.80, 0.00008, 0.00150, 0.20),
    "15m": TimeframeConfig("15m", 30, 0.85, 0.00010, 0.00250, 0.20),
    "30m": TimeframeConfig("30m", 30, 0.85, 0.00012, 0.00350, 0.20),
    "1h": TimeframeConfig("1h", 30, 0.90, 0.00015, 0.00500, 0.20),
    "4h": TimeframeConfig("4h", 30, 0.95, 0.00020, 0.01000, 0.20),
    "1D": TimeframeConfig("1D", 30, 1.00, 0.00030, 0.02000, 0.20),
}


def get_timeframe_config(timeframe: str) -> TimeframeConfig:
    try:
        return _CONFIGS[timeframe]
    except KeyError as exc:
        raise ValueError(
            f"unsupported timeframe: {timeframe!r}; "
            f"use one of {SUPPORTED_TIMEFRAMES}"
        ) from exc


def candle_range(candle: dict) -> float:
    high = float(candle["high"])
    low = float(candle["low"])
    if high < low:
        raise ValueError("candle high must be >= low")
    return high - low


def average_range(candles: list[dict], lookback: int) -> float:
    if lookback < 1:
        raise ValueError("lookback must be >= 1")
    sample = candles[-lookback:]
    if not sample:
        return 0.0
    return sum(candle_range(c) for c in sample) / len(sample)


def adaptive_zone_tolerance(candles: list[dict], timeframe: str) -> float:
    """Return a price-distance suitable for the selected timeframe."""
    config = get_timeframe_config(timeframe)
    value = average_range(candles, config.lookback) * config.range_multiplier
    return min(config.max_zone_distance, max(config.min_zone_distance, value))


def adaptive_confirmation_buffer(candles: list[dict], timeframe: str) -> float:
    """Return the distance required to call a breakout confirmed."""
    config = get_timeframe_config(timeframe)
    value = average_range(candles, config.lookback) * config.confirmation_multiplier
    return max(config.min_zone_distance * 0.5, value)
