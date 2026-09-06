"""Canonical real-time market snapshot.

This module is the shared read-only contract between live analysis,
backtesting, replay, and monitoring. It contains observations only; it never
places orders and never invents future data.
"""

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Any

from strategy.candles import Candle
from strategy.levels_v2 import PriceZone
from strategy.forecast import ForecastResult
from strategy.realtime_guard import DataQuality


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    timeframe: str
    bar_time: datetime
    candle: Candle
    current_close: float
    support: PriceZone | None = None
    resistance: PriceZone | None = None
    forecast: ForecastResult | None = None
    data_quality: DataQuality | None = None
    spread: float | None = None
    latency_seconds: float | None = None

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if self.candle.close != self.current_close:
            raise ValueError("current_close must match candle.close")
        if self.bar_time != self.candle.time:
            raise ValueError("bar_time must match candle.time")
        if self.bar_time.tzinfo is None or self.bar_time.utcoffset() is None:
            raise ValueError("bar_time must be timezone-aware")
        for name, value in (("spread", self.spread), ("latency_seconds", self.latency_seconds)):
            if value is not None and (not isfinite(float(value)) or float(value) < 0):
                raise ValueError(f"{name} must be finite and >= 0")

    @property
    def ready(self) -> bool:
        return self.data_quality is None or self.data_quality.ok

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "bar_time": self.bar_time.isoformat(),
            "open": self.candle.open,
            "high": self.candle.high,
            "low": self.candle.low,
            "close": self.candle.close,
            "spread": self.spread,
            "latency_seconds": self.latency_seconds,
            "has_forecast": self.forecast is not None,
            "data_quality": None if self.data_quality is None else self.data_quality.reason,
        }
