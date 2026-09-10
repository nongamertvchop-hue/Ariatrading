"""MT5 live execution adapter for demo and live Forex execution.

This module is part of the safety-critical live runtime boundary.
It bridges validated strategy signals and risk limits to actual broker orders
via the MetaTrader5 Python API.

All order submissions require pre-validation, mandatory Stop Loss, and
configurable deviation (slippage protection).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Any

from strategy.forex_risk import ForexSymbolContract

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None


ORDER_BUY = "BUY"
ORDER_SELL = "SELL"


@dataclass(frozen=True)
class OrderResult:
    """Standardized result of a broker execution attempt."""

    success: bool
    retcode: int
    ticket: int = 0
    price: float = 0.0
    volume: float = 0.0
    comment: str = ""
    error_message: str = ""


@dataclass(frozen=True)
class PositionSnapshot:
    """Normalized open position representation from MT5."""

    ticket: int
    symbol: str
    order_type: str
    volume: float
    open_price: float
    sl: float
    tp: float
    profit: float
    magic: int
    open_time: datetime


@dataclass(frozen=True)
class AccountSnapshot:
    """Minimal account state required by the live risk boundary."""

    login: int
    balance: float
    equity: float
    margin_free: float
    trade_allowed: bool
    trade_expert: bool


def _resolve_filling_mode(mt5_mod: Any, symbol_info: Any) -> int:
    """Determine best supported order filling mode for the symbol."""
    filling_flags = getattr(symbol_info, "filling_mode", 0)
    order_filling_fok = getattr(mt5_mod, "ORDER_FILLING_FOK", 0)
    order_filling_ioc = getattr(mt5_mod, "ORDER_FILLING_IOC", 1)
    order_filling_return = getattr(mt5_mod, "ORDER_FILLING_RETURN", 2)
    symbol_filling_fok = getattr(mt5_mod, "SYMBOL_FILLING_FOK", 1)
    symbol_filling_ioc = getattr(mt5_mod, "SYMBOL_FILLING_IOC", 2)

    if filling_flags & symbol_filling_fok:
        return order_filling_fok
    if filling_flags & symbol_filling_ioc:
        return order_filling_ioc
    return order_filling_return


class MT5LiveExecutor:
    """Manages broker order submissions and active positions on MT5."""

    def __init__(
        self,
        mt5_module: Any | None = None,
        terminal_path: str | None = None,
        magic_number: int = 8808,
    ) -> None:
        self.mt5 = mt5_module if mt5_module is not None else mt5
        self.terminal_path = terminal_path
        self.magic_number = magic_number
        self._connected = False

    def connect(self) -> bool:
        """Initialize connection to MetaTrader 5."""
        if self.mt5 is None:
            raise RuntimeError("MetaTrader5 package is not installed.")

        if self.terminal_path:
            ok = self.mt5.initialize(path=self.terminal_path)
        else:
            ok = self.mt5.initialize()

        if not ok:
            err = self.mt5.last_error() if hasattr(self.mt5, "last_error") else "unknown error"
            raise RuntimeError(f"Failed to initialize MT5: {err}")

        self._connected = True
        return True

    def disconnect(self) -> None:
        """Shutdown MT5 connection."""
        if self.mt5 is not None and self._connected:
            self.mt5.shutdown()
            self._connected = False

    def get_account_snapshot(self) -> AccountSnapshot:
        """Read account state immediately before live decisions."""
        if not self._connected:
            raise RuntimeError("MT5 executor is not connected.")
        info = self.mt5.account_info()
        if info is None:
            raise RuntimeError(f"MT5 account_info unavailable: {self.mt5.last_error()}")
        return AccountSnapshot(
            login=int(getattr(info, "login", 0)),
            balance=float(getattr(info, "balance", 0.0)),
            equity=float(getattr(info, "equity", 0.0)),
            margin_free=float(getattr(info, "margin_free", 0.0)),
            trade_allowed=bool(getattr(info, "trade_allowed", False)),
            trade_expert=bool(getattr(info, "trade_expert", False)),
        )

    def get_symbol_contract(self, symbol: str) -> ForexSymbolContract:
        """Retrieve and normalize broker contract details for a symbol."""
        if not self._connected:
            raise RuntimeError("MT5 executor is not connected.")

        info = self.mt5.symbol_info(symbol)
        if info is None:
            raise ValueError(f"Symbol {symbol} not found in MT5.")
        if not getattr(info, "visible", True):
            if not self.mt5.symbol_select(symbol, True):
                raise RuntimeError(f"Could not select symbol {symbol} in MT5.")

        return ForexSymbolContract(
            symbol=str(info.name),
            digits=int(info.digits),
            point=float(info.point),
            trade_tick_value=float(info.trade_tick_value),
            trade_tick_size=float(info.trade_tick_size),
            volume_min=float(info.volume_min),
            volume_max=float(info.volume_max),
            volume_step=float(info.volume_step),
        )

    def get_current_tick(self, symbol: str) -> tuple[float, float, datetime]:
        """Fetch current bid, ask, and timestamp."""
        if not self._connected:
            raise RuntimeError("MT5 executor is not connected.")
        tick = self.mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"Could not retrieve tick for {symbol}")
        ts = datetime.fromtimestamp(int(tick.time), tz=timezone.utc)
        return float(tick.bid), float(tick.ask), ts

    def send_market_order(
        self,
        *,
        symbol: str,
        direction: str,
        volume: float,
        sl: float,
        tp: float | None = None,
        deviation_points: int = 20,
        comment: str = "Ariatrading Forex",
    ) -> OrderResult:
        """Execute a market BUY or SELL order with mandatory Stop Loss."""
        if not self._connected:
            return OrderResult(False, -1, error_message="MT5 executor is not connected")
        if direction not in {ORDER_BUY, ORDER_SELL}:
            return OrderResult(False, -1, error_message=f"Invalid direction: {direction}")
        if not isfinite(volume) or volume <= 0:
            return OrderResult(False, -1, error_message="Order volume must be finite and > 0")
        if sl <= 0 or not isfinite(sl):
            return OrderResult(False, -1, error_message="Mandatory Stop Loss must be finite and > 0")
        if tp is not None and (not isfinite(tp) or tp <= 0):
            return OrderResult(False, -1, error_message="Take Profit must be finite and > 0 when provided")
        if deviation_points < 0:
            return OrderResult(False, -1, error_message="Deviation must be >= 0")

        sym_info = self.mt5.symbol_info(symbol)
        if sym_info is None:
            return OrderResult(False, -1, error_message=f"Symbol {symbol} not found")

        filling = _resolve_filling_mode(self.mt5, sym_info)
        tick = self.mt5.symbol_info_tick(symbol)
        if tick is None:
            return OrderResult(False, -1, error_message=f"No tick data for {symbol}")

        if direction == ORDER_BUY:
            order_type = getattr(self.mt5, "ORDER_TYPE_BUY", 0)
            price = float(tick.ask)
            if sl >= price:
                return OrderResult(False, -1, error_message="BUY Stop Loss must be below entry price")
            if tp is not None and tp <= price:
                return OrderResult(False, -1, error_message="BUY Take Profit must be above entry price")
        else:
            order_type = getattr(self.mt5, "ORDER_TYPE_SELL", 1)
            price = float(tick.bid)
            if sl <= price:
                return OrderResult(False, -1, error_message="SELL Stop Loss must be above entry price")
            if tp is not None and tp >= price:
                return OrderResult(False, -1, error_message="SELL Take Profit must be below entry price")

        digits = int(sym_info.digits)
        req = {
            "action": getattr(self.mt5, "TRADE_ACTION_DEAL", 1),
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": round(price, digits),
            "sl": round(sl, digits),
            "deviation": int(deviation_points),
            "magic": self.magic_number,
            "comment": comment,
            "type_time": getattr(self.mt5, "ORDER_TIME_GTC", 0),
            "type_filling": filling,
        }
        if tp is not None:
            req["tp"] = round(tp, digits)

        res = self.mt5.order_send(req)
        if res is None:
            err = self.mt5.last_error() if hasattr(self.mt5, "last_error") else "unknown"
            return OrderResult(False, -1, error_message=f"order_send returned None: {err}")

        trade_retcode_done = getattr(self.mt5, "TRADE_RETCODE_DONE", 10009)
        trade_retcode_placed = getattr(self.mt5, "TRADE_RETCODE_PLACED", 10008)
        if res.retcode in {trade_retcode_done, trade_retcode_placed}:
            return OrderResult(
                success=True,
                retcode=int(res.retcode),
                ticket=int(getattr(res, "order", 0) or getattr(res, "deal", 0)),
                price=float(getattr(res, "price", price)),
                volume=float(getattr(res, "volume", volume)),
                comment=str(getattr(res, "comment", "")),
            )

        return OrderResult(
            success=False,
            retcode=int(res.retcode),
            comment=str(getattr(res, "comment", "")),
            error_message=f"Order rejected by broker (retcode={res.retcode}): {getattr(res, 'comment', '')}",
        )

    def get_open_positions(self, symbol: str | None = None) -> list[PositionSnapshot]:
        """Fetch active positions filtered by this strategy's magic number."""
        if not self._connected:
            return []
        raw_positions = self.mt5.positions_get(symbol=symbol) if symbol else self.mt5.positions_get()
        if raw_positions is None:
            return []

        positions = []
        for pos in raw_positions:
            magic = int(getattr(pos, "magic", 0))
            if self.magic_number and magic != self.magic_number:
                continue
            ptype = getattr(pos, "type", 0)
            otype = ORDER_BUY if ptype == getattr(self.mt5, "ORDER_TYPE_BUY", 0) else ORDER_SELL
            ts = datetime.fromtimestamp(int(pos.time), tz=timezone.utc)
            positions.append(
                PositionSnapshot(
                    ticket=int(pos.ticket),
                    symbol=str(pos.symbol),
                    order_type=otype,
                    volume=float(pos.volume),
                    open_price=float(pos.price_open),
                    sl=float(pos.sl),
                    tp=float(pos.tp),
                    profit=float(pos.profit),
                    magic=magic,
                    open_time=ts,
                )
            )
        return positions

    def close_position(self, ticket: int, deviation_points: int = 20) -> OrderResult:
        """Close an existing open position by ticket."""
        if not self._connected:
            return OrderResult(False, -1, error_message="MT5 executor is not connected")
        positions = self.mt5.positions_get(ticket=ticket)
        if not positions:
            return OrderResult(False, -1, error_message=f"Position ticket {ticket} not found")

        pos = positions[0]
        if self.magic_number and int(getattr(pos, "magic", 0)) != self.magic_number:
            return OrderResult(False, -1, error_message=f"Position #{ticket} is not owned by this strategy")

        sym = str(pos.symbol)
        vol = float(pos.volume)
        ptype = getattr(pos, "type", 0)
        sym_info = self.mt5.symbol_info(sym)
        tick = self.mt5.symbol_info_tick(sym)
        if sym_info is None or tick is None:
            return OrderResult(False, -1, error_message=f"Could not retrieve tick/info for {sym}")

        filling = _resolve_filling_mode(self.mt5, sym_info)
        if ptype == getattr(self.mt5, "ORDER_TYPE_BUY", 0):
            close_type = getattr(self.mt5, "ORDER_TYPE_SELL", 1)
            close_price = float(tick.bid)
        else:
            close_type = getattr(self.mt5, "ORDER_TYPE_BUY", 0)
            close_price = float(tick.ask)

        req = {
            "action": getattr(self.mt5, "TRADE_ACTION_DEAL", 1),
            "position": ticket,
            "symbol": sym,
            "volume": vol,
            "type": close_type,
            "price": round(close_price, int(sym_info.digits)),
            "deviation": int(deviation_points),
            "magic": self.magic_number,
            "comment": f"Close #{ticket}",
            "type_time": getattr(self.mt5, "ORDER_TIME_GTC", 0),
            "type_filling": filling,
        }

        res = self.mt5.order_send(req)
        if res is None or res.retcode != getattr(self.mt5, "TRADE_RETCODE_DONE", 10009):
            err_msg = getattr(res, "comment", "") if res else self.mt5.last_error()
            retcode = getattr(res, "retcode", -1) if res else -1
            return OrderResult(False, retcode, error_message=f"Failed to close #{ticket}: {err_msg}")

        return OrderResult(True, int(res.retcode), ticket=ticket, price=close_price, volume=vol)
