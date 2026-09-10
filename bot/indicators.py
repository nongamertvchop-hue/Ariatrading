from __future__ import annotations

from typing import Sequence


def _talib():
    try:
        import talib  # type: ignore
    except ImportError as exc:
        raise RuntimeError("TA-Lib is not installed; install the bot requirements") from exc
    return talib


def ema(close: Sequence[float], period: int = 20):
    if period < 1:
        raise ValueError("period must be >= 1")
    talib = _talib()
    return talib.EMA(close, timeperiod=period)


def rsi(close: Sequence[float], period: int = 14):
    if period < 1:
        raise ValueError("period must be >= 1")
    talib = _talib()
    return talib.RSI(close, timeperiod=period)


def macd(close: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9):
    if not (1 <= fast < slow) or signal < 1:
        raise ValueError("require 1 <= fast < slow and signal >= 1")
    talib = _talib()
    return talib.MACD(close, fastperiod=fast, slowperiod=slow, signalperiod=signal)


def feature_frame(rows: list[dict]) -> list[dict]:
    """Compute contextual indicators without changing the strategy direction.

    TA-Lib is deliberately isolated here. The core price-action strategy does
    not import this module, so indicator experimentation cannot silently create
    a third setup or leak into execution decisions.
    """
    close = [float(row["close"]) for row in rows]
    ema20 = ema(close, 20)
    rsi14 = rsi(close, 14)
    macd_line, macd_signal, macd_hist = macd(close)
    result = []
    for i, row in enumerate(rows):
        item = dict(row)
        item.update({
            "ema20": None if ema20[i] != ema20[i] else float(ema20[i]),
            "rsi14": None if rsi14[i] != rsi14[i] else float(rsi14[i]),
            "macd": None if macd_line[i] != macd_line[i] else float(macd_line[i]),
            "macd_signal": None if macd_signal[i] != macd_signal[i] else float(macd_signal[i]),
            "macd_hist": None if macd_hist[i] != macd_hist[i] else float(macd_hist[i]),
        })
        result.append(item)
    return result
