"""Leakage-safe feature construction for the Ariatrading ML research layer.

Every feature is computed from candles at or before the decision index. Future
candles are used only to construct the supervised label.
"""

from dataclasses import dataclass
from math import isfinite

from .engine import EngineSignal, LONG, SHORT

FEATURE_NAMES = (
    "direction",
    "setup_score",
    "zone_touches",
    "distance_to_zone",
    "body_pct",
    "range_pct",
    "upper_wick_pct",
    "lower_wick_pct",
    "close_location",
    "return_1",
    "return_3",
    "return_5",
    "volatility_5",
)


@dataclass(frozen=True)
class MLSample:
    index: int
    timestamp: object
    features: tuple[float, ...]
    label: int


def _finite(value: float, name: str) -> float:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _safe_ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _returns(closes: list[float], index: int, lookback: int) -> float:
    if index < lookback:
        return 0.0
    base = closes[index - lookback]
    return _safe_ratio(closes[index] - base, base) if base else 0.0


def _volatility(closes: list[float], index: int, window: int = 5) -> float:
    start = max(0, index - window + 1)
    values = []
    for i in range(start + 1, index + 1):
        previous = closes[i - 1]
        if previous:
            values.append((closes[i] - previous) / previous)
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return (sum((value - mean) ** 2 for value in values) / len(values)) ** 0.5


def extract_signal_features(candles: list[dict], index: int, signal: EngineSignal) -> tuple[float, ...]:
    """Build a fixed feature vector using only the supplied historical prefix."""
    if signal.action not in {LONG, SHORT}:
        raise ValueError("signal must be LONG or SHORT")
    if not 0 <= index < len(candles):
        raise ValueError("index must be within candles")
    candle = candles[index]
    open_price = float(candle["open"])
    high = float(candle["high"])
    low = float(candle["low"])
    close = float(candle["close"])
    candle_range = high - low
    if candle_range <= 0:
        raise ValueError("candle high must be greater than low")
    if open_price <= 0 or close <= 0:
        raise ValueError("open and close must be > 0")

    body = abs(close - open_price)
    upper_wick = high - max(open_price, close)
    lower_wick = min(open_price, close) - low
    score = signal.score.total / 100.0 if signal.score is not None else 0.0
    zone_touches = float(signal.zone.touches) if signal.zone is not None else 0.0
    if signal.zone is None:
        distance_to_zone = 0.0
    else:
        distance_to_zone = abs(close - signal.zone.center) / candle_range

    closes = [float(raw["close"]) for raw in candles[: index + 1]]
    direction = 1.0 if signal.action == LONG else -1.0
    features = (
        direction,
        score,
        zone_touches,
        distance_to_zone,
        body / candle_range,
        candle_range / close,
        upper_wick / candle_range,
        lower_wick / candle_range,
        (close - low) / candle_range,
        _returns(closes, index, 1),
        _returns(closes, index, 3),
        _returns(closes, index, 5),
        _volatility(closes, index),
    )
    return tuple(_finite(value, name) for value, name in zip(features, FEATURE_NAMES))


def build_signal_sample(
    candles: list[dict],
    index: int,
    signal: EngineSignal,
    *,
    horizon_bars: int = 3,
    favorable_move: float = 0.0,
) -> MLSample:
    """Create one label from future movement after a leakage-safe feature prefix.

    The label is 1 when future close-to-close movement in the signal direction
    exceeds ``favorable_move``. This label is intentionally a market follow-
    through target, not a claim of profit or a calibrated win probability.
    """
    if horizon_bars < 1:
        raise ValueError("horizon_bars must be >= 1")
    if favorable_move < 0:
        raise ValueError("favorable_move must be >= 0")
    if index + horizon_bars >= len(candles):
        raise ValueError("not enough future candles to build label")

    features = extract_signal_features(candles, index, signal)
    current_close = float(candles[index]["close"])
    future_close = float(candles[index + horizon_bars]["close"])
    if current_close <= 0:
        raise ValueError("current close must be > 0")
    signed_move = (future_close - current_close) / current_close
    if signal.action == SHORT:
        signed_move = -signed_move
    label = int(signed_move > favorable_move)
    return MLSample(index=index, timestamp=candles[index].get("time"), features=features, label=label)


__all__ = ["FEATURE_NAMES", "MLSample", "build_signal_sample", "extract_signal_features"]
