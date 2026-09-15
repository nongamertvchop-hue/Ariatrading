"""Deterministic, causal technical-indicator calculations for research/paper trading.

The functions in this module consume OHLC candles in chronological order and
never inspect future candles.  They intentionally use no third-party package so
the same formulas can be validated in CI and mirrored by the Worker runtime.

Indicators are evidence/context only.  This module does not create LONG/SHORT
signals and does not place orders.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence


Candle = dict[str, float]


@dataclass(frozen=True)
class IndicatorSnapshot:
    """Latest indicator values available at the last supplied closed candle."""

    ema20: float | None
    ema50: float | None
    ema200: float | None
    rsi14: float | None
    atr14: float | None
    adx14: float | None
    macd: float | None
    macd_signal: float | None
    macd_histogram: float | None


def _value(candle: Candle, key: str) -> float:
    value = float(candle[key])
    if not isfinite(value):
        raise ValueError(f"{key} must be finite")
    return value


def _closes(candles: Sequence[Candle]) -> list[float]:
    return [_value(candle, "close") for candle in candles]


def _validate_period(period: int) -> None:
    if period < 1:
        raise ValueError("period must be >= 1")


def _sma(values: Sequence[float], period: int) -> float | None:
    _validate_period(period)
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def ema_series(candles: Sequence[Candle], period: int) -> list[float | None]:
    """Return a causally seeded EMA series; values before warm-up are None."""
    _validate_period(period)
    closes = _closes(candles)
    result: list[float | None] = [None] * len(closes)
    if len(closes) < period:
        return result

    ema = sum(closes[:period]) / period
    result[period - 1] = ema
    alpha = 2.0 / (period + 1.0)
    for index in range(period, len(closes)):
        ema = (closes[index] - ema) * alpha + ema
        result[index] = ema
    return result


def ema(candles: Sequence[Candle], period: int) -> float | None:
    series = ema_series(candles, period)
    return series[-1] if series else None


def rsi_series(candles: Sequence[Candle], period: int = 14) -> list[float | None]:
    """Return Wilder RSI, with the first value available after `period` changes."""
    _validate_period(period)
    closes = _closes(candles)
    result: list[float | None] = [None] * len(closes)
    if len(closes) <= period:
        return result

    gains = [max(closes[i] - closes[i - 1], 0.0) for i in range(1, len(closes))]
    losses = [max(closes[i - 1] - closes[i], 0.0) for i in range(1, len(closes))]
    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period

    def to_rsi(gain: float, loss: float) -> float:
        if loss == 0.0:
            return 100.0 if gain > 0.0 else 50.0
        if gain == 0.0:
            return 0.0
        return 100.0 - (100.0 / (1.0 + gain / loss))

    result[period] = to_rsi(average_gain, average_loss)
    for index in range(period + 1, len(closes)):
        average_gain = ((average_gain * (period - 1)) + gains[index - 1]) / period
        average_loss = ((average_loss * (period - 1)) + losses[index - 1]) / period
        result[index] = to_rsi(average_gain, average_loss)
    return result


def rsi(candles: Sequence[Candle], period: int = 14) -> float | None:
    series = rsi_series(candles, period)
    return series[-1] if series else None


def true_range_series(candles: Sequence[Candle]) -> list[float]:
    if not candles:
        return []
    result: list[float] = []
    previous_close: float | None = None
    for candle in candles:
        high = _value(candle, "high")
        low = _value(candle, "low")
        if high < low:
            raise ValueError("high must be >= low")
        if previous_close is None:
            value = high - low
        else:
            value = max(high - low, abs(high - previous_close), abs(low - previous_close))
        result.append(value)
        previous_close = _value(candle, "close")
    return result


def atr_series(candles: Sequence[Candle], period: int = 14) -> list[float | None]:
    """Return Wilder ATR, seeded from the first `period` true ranges."""
    _validate_period(period)
    ranges = true_range_series(candles)
    result: list[float | None] = [None] * len(ranges)
    if len(ranges) < period:
        return result

    average = sum(ranges[:period]) / period
    result[period - 1] = average
    for index in range(period, len(ranges)):
        average = ((average * (period - 1)) + ranges[index]) / period
        result[index] = average
    return result


def atr(candles: Sequence[Candle], period: int = 14) -> float | None:
    series = atr_series(candles, period)
    return series[-1] if series else None


def _wilder_smooth(values: Sequence[float], period: int) -> list[float | None]:
    _validate_period(period)
    result: list[float | None] = [None] * len(values)
    if len(values) < period:
        return result
    smoothed = sum(values[:period]) / period
    result[period - 1] = smoothed
    for index in range(period, len(values)):
        smoothed = ((smoothed * (period - 1)) + values[index]) / period
        result[index] = smoothed
    return result


def adx_series(candles: Sequence[Candle], period: int = 14) -> list[float | None]:
    """Return Wilder ADX using the standard +DI/-DI directional movement."""
    _validate_period(period)
    if not candles:
        return []
    highs = [_value(candle, "high") for candle in candles]
    lows = [_value(candle, "low") for candle in candles]
    closes = _closes(candles)
    if len(candles) < (period * 2):
        return [None] * len(candles)

    tr = true_range_series(candles)
    plus_dm = [0.0]
    minus_dm = [0.0]
    for index in range(1, len(candles)):
        up = highs[index] - highs[index - 1]
        down = lows[index - 1] - lows[index]
        plus_dm.append(up if up > down and up > 0.0 else 0.0)
        minus_dm.append(down if down > up and down > 0.0 else 0.0)

    smoothed_tr = _wilder_smooth(tr, period)
    smoothed_plus = _wilder_smooth(plus_dm, period)
    smoothed_minus = _wilder_smooth(minus_dm, period)
    dx: list[float | None] = [None] * len(candles)
    for index in range(len(candles)):
        tr_value = smoothed_tr[index]
        plus_value = smoothed_plus[index]
        minus_value = smoothed_minus[index]
        if tr_value is None or plus_value is None or minus_value is None or tr_value == 0.0:
            continue
        plus_di = 100.0 * plus_value / tr_value
        minus_di = 100.0 * minus_value / tr_value
        denominator = plus_di + minus_di
        dx[index] = 0.0 if denominator == 0.0 else 100.0 * abs(plus_di - minus_di) / denominator

    available = [value for value in dx if value is not None]
    if len(available) < period:
        return [None] * len(candles)

    first_dx_index = next(index for index, value in enumerate(dx) if value is not None)
    adx_values = [None] * len(candles)
    seed_end = first_dx_index + period
    if seed_end > len(candles):
        return adx_values
    seed = [value for value in dx[first_dx_index:seed_end] if value is not None]
    if len(seed) < period:
        return adx_values
    current = sum(seed) / period
    adx_values[seed_end - 1] = current
    for index in range(seed_end, len(candles)):
        value = dx[index]
        if value is None:
            continue
        current = ((current * (period - 1)) + value) / period
        adx_values[index] = current
    return adx_values


def adx(candles: Sequence[Candle], period: int = 14) -> float | None:
    series = adx_series(candles, period)
    return series[-1] if series else None


def macd_series(
    candles: Sequence[Candle],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Return MACD line, signal line and histogram without future leakage."""
    if fast_period >= slow_period:
        raise ValueError("fast_period must be < slow_period")
    _validate_period(fast_period)
    _validate_period(slow_period)
    _validate_period(signal_period)

    fast = ema_series(candles, fast_period)
    slow = ema_series(candles, slow_period)
    line: list[float | None] = [None] * len(candles)
    compact: list[float] = []
    compact_indices: list[int] = []
    for index, (fast_value, slow_value) in enumerate(zip(fast, slow)):
        if fast_value is None or slow_value is None:
            continue
        value = fast_value - slow_value
        line[index] = value
        compact.append(value)
        compact_indices.append(index)

    signal_compact: list[float | None] = [None] * len(compact)
    if len(compact) >= signal_period:
        current = sum(compact[:signal_period]) / signal_period
        signal_compact[signal_period - 1] = current
        alpha = 2.0 / (signal_period + 1.0)
        for index in range(signal_period, len(compact)):
            current = (compact[index] - current) * alpha + current
            signal_compact[index] = current

    signal: list[float | None] = [None] * len(candles)
    histogram: list[float | None] = [None] * len(candles)
    for compact_index, candle_index in enumerate(compact_indices):
        signal_value = signal_compact[compact_index]
        signal[candle_index] = signal_value
        if signal_value is not None and line[candle_index] is not None:
            histogram[candle_index] = line[candle_index] - signal_value
    return line, signal, histogram


def macd(candles: Sequence[Candle]) -> tuple[float | None, float | None, float | None]:
    line, signal, histogram = macd_series(candles)
    if not candles:
        return None, None, None
    return line[-1], signal[-1], histogram[-1]


def calculate_indicators(candles: Sequence[Candle]) -> IndicatorSnapshot:
    """Calculate the default production research set from closed candles only."""
    macd_value, macd_signal, macd_histogram = macd(candles)
    return IndicatorSnapshot(
        ema20=ema(candles, 20),
        ema50=ema(candles, 50),
        ema200=ema(candles, 200),
        rsi14=rsi(candles, 14),
        atr14=atr(candles, 14),
        adx14=adx(candles, 14),
        macd=macd_value,
        macd_signal=macd_signal,
        macd_histogram=macd_histogram,
    )
