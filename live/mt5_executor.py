"""MT5 live execution adapter for demo and live Forex execution.

This module is the safety-critical broker boundary. It validates the order,
refreshes the broker tick, runs MT5's order_check() before order_send(), and
never treats an unknown broker outcome as a safe retry.
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
    success: bool
    retcode: int
    ticket: int = 0
    price: float = 0.0
    volume: float = 0.0
    comment: str = ""
    error_message: str = ""


@dataclass(frozen=True)
class PositionSnapshot:
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
    login: int
    balance: float
    equity: float
    margin_free: float
    trade_allowed: bool
    trade_expert: bool


def _resolve_filling_mode(mt5_mod: Any, symbol_info: Any) -> int:
    """Determine the first filling mode explicitly supported by the broker."""
    flags = int(getattr(symbol_info, "filling_mode", 0))
    fok_flag = int(getattr(mt5_mod, "SYMBOL_FILLING_FOK", 1))
    ioc_flag = int(getattr(mt5_mod, "SYMBOL_FILLING_IOC", 2))
    if flags & fok_flag:
        return int(getattr(mt5_mod, "ORDER_FILLING_FOK", 0))
    if flags & ioc_flag:
        return int(getattr(mt5_mod, "ORDER_FILLING_IOC", 1))
    return int(getattr(mt5_mod, "ORDER_FILLING_RETURN", 2))


class MT5LiveExecutor:
    """Manage broker order submissions and positions on a connected MT5 terminal."""

    def __init__(self, mt5_module: Any | None = None, terminal_path: str | None = None, magic_number: int = 8808) -> None:
        self.mt5 = mt5_module if mt5_module is not None else mt5
        self.terminal_path = terminal_path
        self.magic_number = magic_number
        self._connected = False

    def connect(self) -> bool:
        if self.mt5 is None:
            raise RuntimeError("MetaTrader5 package is not installed.")
        ok = self.mt5.initialize(path=self.terminal_path) if self.terminal_path else self.mt5.initialize()
        if not ok:
            err = self.mt5.last_error() if hasattr(self.mt5, "last_error") else "unknown error"
            raise RuntimeError(f"Failed to initialize MT5: {err}")
        self._connected = True
        return True

    def disconnect(self) -> None:
        if self.mt5 is not None and self._connected:
            self.mt5.shutdown()
            self._connected = False

    def get_account_snapshot(self) -> AccountSnapshot:
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
        if not self._connected:
            raise RuntimeError("MT5 executor is not connected.")
        info = self.mt5.symbol_info(symbol)
        if info is None:
            raise ValueError(f"Symbol {symbol} not found in MT5.")
        if not getattr(info, "visible", True) and not self.mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Could not select symbol {symbol} in MT5.")
        return ForexSymbolContract(
            symbol=str(info.name), digits=int(info.digits), point=float(info.point),
            trade_tick_value=float(info.trade_tick_value), trade_tick_size=float(info.trade_tick_size),
            volume_min=float(info.volume_min), volume_max=float(info.volume_max), volume_step=float(info.volume_step),
        )

    def get_current_tick(self, symbol: str) -> tuple[float, float, datetime]:
        if not self._connected:
            raise RuntimeError("MT5 executor is not connected.")
        tick = self.mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"Could not retrieve tick for {symbol}")
        return float(tick.bid), float(tick.ask), datetime.fromtimestamp(int(tick.time), tz=timezone.utc)

    @staticmethod
    def _valid_step_volume(volume: float, minimum: float, maximum: float, step: float) -> bool:
        if not all(isfinite(v) and v > 0 for v in (volume, minimum, maximum, step)):
            return False
        if volume < minimum - 1e-9 or volume > maximum + 1e-9:
            return False
        steps = (volume - minimum) / step
        return abs(steps - round(steps)) <= 1e-7

    def send_market_order(
        self, *, symbol: str, direction: str, volume: float, sl: float,
        tp: float | None = None, deviation_points: int = 20,
        comment: str = "Ariatrading Forex",
    ) -> OrderResult:
        """Validate, order_check, then submit one market order.

        A failed/unknown order_check never reaches order_send. Any exception
        from order_send is allowed to become AMBIGUOUS in the caller because
        transport failure cannot prove that the broker rejected the request.
        """
        if not self._connected:
            return OrderResult(False, -1, error_message="MT5 executor is not connected")
        if direction not in {ORDER_BUY, ORDER_SELL}:
            return OrderResult(False, -1, error_message=f"Invalid direction: {direction}")
        if not isfinite(volume) or volume <= 0:
            return OrderResult(False, -1, error_message="Order volume must be finite and > 0")
        if not isfinite(sl) or sl <= 0:
            return OrderResult(False, -1, error_message="Mandatory Stop Loss must be finite and > 0")
        if tp is not None and (not isfinite(tp) or tp <= 0):
            return OrderResult(False, -1, error_message="Take Profit must be finite and > 0 when provided")
        if deviation_points < 0:
            return OrderResult(False, -1, error_message="Deviation must be >= 0")

        info = self.mt5.symbol_info(symbol)
        if info is None:
            return OrderResult(False, -1, error_message=f"Symbol {symbol} not found")
        if not getattr(info, "visible", True) and not self.mt5.symbol_select(symbol, True):
            return OrderResult(False, -1, error_message=f"Could not select symbol {symbol}")
        if not self._valid_step_volume(volume, float(info.volume_min), float(info.volume_max), float(info.volume_step)):
            return OrderResult(False, -1, error_message="Order volume violates broker min/max/step constraints")

        tick = self.mt5.symbol_info_tick(symbol)
        if tick is None:
            return OrderResult(False, -1, error_message=f"No tick data for {symbol}")
        filling = _resolve_filling_mode(self.mt5, info)
        digits = int(info.digits)

        if direction == ORDER_BUY:
            order_type = int(getattr(self.mt5, "ORDER_TYPE_BUY", 0))
            price = float(tick.ask)
            if sl >= price:
                return OrderResult(False, -1, error_message="BUY Stop Loss must be below entry price")
            if tp is not None and tp <= price:
                return OrderResult(False, -1, error_message="BUY Take Profit must be above entry price")
        else:
            order_type = int(getattr(self.mt5, "ORDER_TYPE_SELL", 1))
            price = float(tick.bid)
            if sl <= price:
                return OrderResult(False, -1, error_message="SELL Stop Loss must be above entry price")
            if tp is not None and tp >= price:
                return OrderResult(False, -1, error_message="SELL Take Profit must be below entry price")

        req = {
            "action": int(getattr(self.mt5, "TRADE_ACTION_DEAL", 1)),
            "symbol": symbol, "volume": float(volume), "type": order_type,
            "price": round(price, digits), "sl": round(sl, digits),
            "deviation": int(deviation_points), "magic": self.magic_number,
            "comment": comment, "type_time": int(getattr(self.mt5, "ORDER_TIME_GTC", 0)),
            "type_filling": filling,
        }
        if tp is not None:
            req["tp"] = round(tp, digits)

        check = self.mt5.order_check(req)
        if check is None:
            err = self.mt5.last_error() if hasattr(self.mt5, "last_error") else "unknown"
            return OrderResult(False, -1, error_message=f"order_check returned None: {err}")
        check_retcode = int(getattr(check, "retcode", -1))
        check_done = int(getattr(self.mt5, "TRADE_RETCODE_DONE", 10009))
        if check_retcode not in {0, check_done}:
            return OrderResult(False, check_retcode, comment=str(getattr(check, "comment", "")), error_message=f"MT5 order_check rejected request (retcode={check_retcode}): {getattr(check, 'comment', '')}")

        res = self.mt5.order_send(req)
        if res is None:
            err = self.mt5.last_error() if hasattr(self.mt5, "last_error") else "unknown"
            raise RuntimeError(f"order_send returned None: {err}")

        retcode = int(getattr(res, "retcode", -1))
        done = int(getattr(self.mt5, "TRADE_RETCODE_DONE", 10009))
        placed = int(getattr(self.mt5, "TRADE_RETCODE_PLACED", 10008))
        if retcode in {done, placed}:
            return OrderResult(True, retcode, ticket=int(getattr(res, "order", 0) or getattr(res, "deal", 0)), price=float(getattr(res, "price", price)), volume=float(getattr(res, "volume", volume)), comment=str(getattr(res, "comment", "")))
        return OrderResult(False, retcode, comment=str(getattr(res, "comment", "")), error_message=f"Order rejected by broker (retcode={retcode}): {getattr(res, 'comment', '')}")

    def get_open_positions(self, symbol: str | None = None) -> list[PositionSnapshot]:
        if not self._connected:
            raise RuntimeError("MT5 executor is not connected")
        raw = self.mt5.positions_get(symbol=symbol) if symbol else self.mt5.positions_get()
        if raw is None:
            raise RuntimeError(f"MT5 positions_get failed: {self.mt5.last_error()}")
        result = []
        for pos in raw:
            magic = int(getattr(pos, "magic", 0))
            if self.magic_number and magic != self.magic_number:
                continue
            ptype = getattr(pos, "type", 0)
            otype = ORDER_BUY if ptype == getattr(self.mt5, "ORDER_TYPE_BUY", 0) else ORDER_SELL
            result.append(PositionSnapshot(
                ticket=int(pos.ticket), symbol=str(pos.symbol), order_type=otype,
                volume=float(pos.volume), open_price=float(pos.price_open), sl=float(pos.sl), tp=float(pos.tp),
                profit=float(pos.profit), magic=magic,
                open_time=datetime.fromtimestamp(int(pos.time), tz=timezone.utc),
            ))
        return result

    def close_position(self, ticket: int, deviation_points: int = 20) -> OrderResult:
        if not self._connected:
            return OrderResult(False, -1, error_message="MT5 executor is not connected")
        positions = self.mt5.positions_get(ticket=ticket)
        if positions is None:
            return OrderResult(False, -1, error_message=f"MT5 position lookup failed: {self.mt5.last_error()}")
        if not positions:
            return OrderResult(False, -1, error_message=f"Position ticket {ticket} not found")
        pos = positions[0]
        if self.magic_number and int(getattr(pos, "magic", 0)) != self.magic_number:
            return OrderResult(False, -1, error_message=f"Position #{ticket} is not owned by this strategy")
        sym = str(pos.symbol)
        info = self.mt5.symbol_info(sym)
        tick = self.mt5.symbol_info_tick(sym)
        if info is None or tick is None:
            return OrderResult(False, -1, error_message=f"Could not retrieve tick/info for {sym}")
        ptype = getattr(pos, "type", 0)
        close_type = int(getattr(self.mt5, "ORDER_TYPE_SELL", 1)) if ptype == getattr(self.mt5, "ORDER_TYPE_BUY", 0) else int(getattr(self.mt5, "ORDER_TYPE_BUY", 0))
        close_price = float(tick.bid) if close_type == getattr(self.mt5, "ORDER_TYPE_SELL", 1) else float(tick.ask)
        req = {
            "action": int(getattr(self.mt5, "TRADE_ACTION_DEAL", 1)), "position": ticket, "symbol": sym,
            "volume": float(pos.volume), "type": close_type, "price": round(close_price, int(info.digits)),
            "deviation": int(deviation_points), "magic": self.magic_number, "comment": f"Close #{ticket}",
            "type_time": int(getattr(self.mt5, "ORDER_TIME_GTC", 0)), "type_filling": _resolve_filling_mode(self.mt5, info),
        }
        check = self.mt5.order_check(req)
        if check is None:
            return OrderResult(False, -1, error_message=f"close order_check returned None: {self.mt5.last_error()}")
        check_retcode = int(getattr(check, "retcode", -1))
        if check_retcode not in {0, int(getattr(self.mt5, "TRADE_RETCODE_DONE", 10009))}:
            return OrderResult(False, check_retcode, error_message=f"Close order_check rejected request: {getattr(check, 'comment', '')}")
        res = self.mt5.order_send(req)
        if res is None:
            raise RuntimeError(f"close order_send returned None: {self.mt5.last_error()}")
        if int(res.retcode) != int(getattr(self.mt5, "TRADE_RETCODE_DONE", 10009)):
            return OrderResult(False, int(res.retcode), error_message=f"Failed to close #{ticket}: {getattr(res, 'comment', '')}")
        return OrderResult(True, int(res.retcode), ticket=ticket, price=close_price, volume=float(pos.volume))
