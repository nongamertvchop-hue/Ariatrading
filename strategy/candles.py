"""Candle structure analysis for the price-action strategy.

No technical indicators are used here. The module only evaluates OHLC data.
"""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Candle:
    open: float
    high: float
    low: float
    close: float

    def __post_init__(self):
        values = {
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
        }
        if any(not isfinite(value) for value in values.values()):
            raise ValueError("OHLC values must be finite")
        if self.high < max(self.open, self.close):
            raise ValueError("high must be >= open and close")
        if self.low > min(self.open, self.close):
            raise ValueError("low must be <= open and close")
        if self.high < self.low:
            raise ValueError("high must be >= low")

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low

    @property
    def bullish(self) -> bool:
        return self.close > self.open

    @property
    def bearish(self) -> bool:
        return self.close < self.open

    @property
    def body_ratio(self) -> float:
        return self.body / self.range if self.range else 0.0

    @property
    def close_position(self) -> float:
        """0 = close at low, 1 = close at high."""
        return (self.close - self.low) / self.range if self.range else 0.5


def candle_pressure(candle: Candle) -> str:
    """Classify the candle as buying, selling, or neutral pressure.

    This is deliberately a simple first version. It describes the completed
    candle; it is not a prediction of the next candle.
    """
    if candle.range == 0:
        return "NEUTRAL"

    # A close near the high with a bullish body favors buyers.
    if candle.bullish and candle.close_position >= 0.70:
        return "BUYING"

    # A close near the low with a bearish body favors sellers.
    if candle.bearish and candle.close_position <= 0.30:
        return "SELLING"

    return "NEUTRAL"


def rejection_pressure(candle: Candle, direction: str) -> bool:
    """Return whether OHLC shows directional rejection at a tested level.

    No volatility indicator or learned threshold is used. The existing
    directional pressure is combined with a dominant wick on the tested side.
    """
    if direction == "LONG":
        return (
            candle_pressure(candle) == "BUYING"
            and candle.lower_wick >= candle.upper_wick
        )
    if direction == "SHORT":
        return (
            candle_pressure(candle) == "SELLING"
            and candle.upper_wick >= candle.lower_wick
        )
    raise ValueError("direction must be LONG or SHORT")
