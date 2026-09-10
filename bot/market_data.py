from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .rate_limit import TokenBucket


_TIMEFRAME_ATTR = {"1m": "TIMEFRAME_M1", "5m": "TIMEFRAME_M5", "15m": "TIMEFRAME_M15", "30m": "TIMEFRAME_M30", "1h": "TIMEFRAME_H1", "4h": "TIMEFRAME_H4", "1D": "TIMEFRAME_D1"}


class MT5OHLCV:
    """Canonical OHLCV reader for research/monitoring; excludes the forming bar."""

    def __init__(self, mt5_module: Any, limiter: TokenBucket | None = None) -> None:
        self.mt5 = mt5_module
        self.limiter = limiter or TokenBucket()

    def dataframe(self, symbol: str, timeframe: str, limit: int = 500):
        if timeframe not in _TIMEFRAME_ATTR:
            raise ValueError(f"unsupported timeframe: {timeframe}")
        if limit < 1:
            raise ValueError("limit must be >= 1")
        self.limiter.wait()
        rates = self.mt5.copy_rates_from_pos(symbol, getattr(self.mt5, _TIMEFRAME_ATTR[timeframe]), 1, limit)
        if rates is None:
            raise RuntimeError(f"MT5 OHLCV request failed: {self.mt5.last_error()}")
        try:
            import pandas as pd
        except ImportError as exc:
            raise RuntimeError("pandas is required for the OHLCV dataframe layer") from exc
        frame = pd.DataFrame(rates)
        if frame.empty:
            return frame
        frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
        frame = frame.rename(columns={"tick_volume": "volume_tick", "real_volume": "volume_real"})
        frame["volume"] = frame["volume_real"].where(frame["volume_real"] > 0, frame["volume_tick"])
        required = ["time", "open", "high", "low", "close", "volume"]
        frame = frame[required].sort_values("time").drop_duplicates("time", keep="last").reset_index(drop=True)
        frame.attrs["symbol"] = symbol
        frame.attrs["timeframe"] = timeframe
        frame.attrs["retrieved_at"] = datetime.now(timezone.utc).isoformat()
        return frame
