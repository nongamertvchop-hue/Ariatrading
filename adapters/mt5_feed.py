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
    """Read completed and forming OHLC bars from a connected MT5 terminal."""

    def __init__(
        self,
        mt5_module: Any | None = None,
        terminal_path: str | None = None,
        manage_connection: bool = True,
    ):
        """Create a feed; optionally borrow an already-connected MT5 session."""
        self.mt5 = mt5 if mt5_module is None else mt5_module
        self._manage_connection = manage_connection
        if self.mt5 is None:
            _require_mt5()
        if not self._manage_connection:
            return

        if terminal_path:
            ok = self.mt5.initialize(path=terminal_path)
        else:
            ok = self.mt5.initialize()
        if not ok:
            raise RuntimeError(f"MT5 initialize failed: {self.mt5.last_error()}")

    def close(self) -> None:
        """Close the MT5 terminal connection only when this feed owns it."""
        if self.mt5 is None:
            _require_mt5()
        if self._manage_connection:
            self.mt5.shutdown()

    def _timeframe(self, timeframe: str) -> Any:
        if self.mt5 is None:
            _require_mt5()
        try:
            return getattr(self.mt5, _TIMEFRAME_MAP[timeframe])
        except KeyError as exc:
            raise ValueError(f"unsupported timeframe: {timeframe}") from exc

    @staticmethod
    def _bar(row: Any) -> LiveBar:
        return LiveBar(
            time=datetime.fromtimestamp(int(row["time"]), tz=timezone.utc),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
        )

    def closed_bars(self, symbol: str, timeframe: str, count: int) -> list[LiveBar]:
        """Return only completed candles; the forming bar is excluded."""
        if self.mt5 is None:
            _require_mt5()
        if count < 1:
            raise ValueError("count must be positive")

        rates = self.mt5.copy_rates_from_pos(symbol, self._timeframe(timeframe), 1, count)
        if rates is None:
            raise RuntimeError(f"MT5 rates request failed: {self.mt5.last_error()}")

        bars = [self._bar(row) for row in rates]
        bars.sort(key=lambda b: b.time)
        return bars

    def current_bar(self, symbol: str, timeframe: str) -> LiveBar:
        """Return the currently forming candle for chart display only."""
        if self.mt5 is None:
            _require_mt5()
        rates = self.mt5.copy_rates_from_pos(symbol, self._timeframe(timeframe), 0, 1)
        if rates is None or len(rates) != 1:
            raise RuntimeError(f"MT5 current bar request failed: {self.mt5.last_error()}")
        return self._bar(rates[0])

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
