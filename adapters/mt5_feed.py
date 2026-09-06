"""MetaTrader 5 market-data adapter for realtime research monitoring.

The MetaTrader5 Python package is optional. Core strategy, backtest, and
research code must remain usable on platforms where MT5 is unavailable.
This adapter is read-only and never calls order_send().
"""

from datetime import datetime, timezone
from typing import Any

from strategy.realtime import LiveBar

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None


_TIMEFRAME_MAP = {
    "1m": "TIMEFRAME_M1",
    "5m": "TIMEFRAME_M5",
    "15m": "TIMEFRAME_M15",
    "30m": "TIMEFRAME_M30",
    "1h": "TIMEFRAME_H1",
    "4h": "TIMEFRAME_H4",
    "1D": "TIMEFRAME_D1",
}


def _require_mt5() -> None:
    """Fail clearly when the optional MT5 dependency is unavailable."""
    if mt5 is None:
        raise RuntimeError(
            "MetaTrader5 package ไม่พร้อมใช้งาน (รองรับเฉพาะ Windows ที่มี MT5 terminal ติดตั้งอยู่) "
            "ฟีเจอร์ realtime feed นี้จึงใช้ไม่ได้บนเครื่อง/แอปนี้"
        )


class MT5BarFeed:
    """Read completed OHLC bars from a connected MetaTrader 5 terminal."""

    def __init__(self, mt5_module: Any | None = None, terminal_path: str | None = None):
        """Create a feed, using an injected module for tests when provided."""
        self.mt5 = mt5 if mt5_module is None else mt5_module
        if self.mt5 is None:
            _require_mt5()

        if terminal_path:
            ok = self.mt5.initialize(path=terminal_path)
        else:
            ok = self.mt5.initialize()
        if not ok:
            raise RuntimeError(f"MT5 initialize failed: {self.mt5.last_error()}")

    def close(self) -> None:
        """Close the MT5 terminal connection."""
        if self.mt5 is None:
            _require_mt5()
        self.mt5.shutdown()

    def closed_bars(self, symbol: str, timeframe: str, count: int) -> list[LiveBar]:
        """Return only completed candles; the forming bar is excluded."""
        if self.mt5 is None:
            _require_mt5()
        if timeframe not in _TIMEFRAME_MAP:
            raise ValueError(f"unsupported timeframe: {timeframe}")
        if count < 1:
            raise ValueError("count must be positive")

        tf = getattr(self.mt5, _TIMEFRAME_MAP[timeframe])
        # Position 0 is the currently forming bar. Start at 1 so only closed
        # candles enter the strategy and live monitoring cannot use intrabar data.
        rates = self.mt5.copy_rates_from_pos(symbol, tf, 1, count)
        if rates is None:
            raise RuntimeError(f"MT5 rates request failed: {self.mt5.last_error()}")

        bars = []
        for row in rates:
            ts = datetime.fromtimestamp(int(row["time"]), tz=timezone.utc)
            bars.append(
                LiveBar(
                    time=ts,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                )
            )
        bars.sort(key=lambda b: b.time)
        return bars

    def last_tick(self, symbol: str) -> dict:
        """Return the latest tick for monitoring only; no order functionality."""
        if self.mt5 is None:
            _require_mt5()
        tick = self.mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"MT5 tick request failed: {self.mt5.last_error()}")
        return {
            "time": datetime.fromtimestamp(int(tick.time), tz=timezone.utc),
            "bid": float(tick.bid),
            "ask": float(tick.ask),
            "last": float(tick.last),
            "volume": int(tick.volume),
        }
