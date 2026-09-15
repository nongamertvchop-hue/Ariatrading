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


@dataclass(frozen=True)
class AccountIdentity:
    """Stable broker/account identity used to prevent runtime account drift."""

    login: int
    server: str
    company: str
    trade_mode: int


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

    def __init__(
        self,
        mt5_module: Any | None = None,
        terminal_path: str | None = None,
        magic_number: int = 8808,
        login: int | None = None,
        password: str = "",
        server: str = "",
    ) -> None:
        self.mt5 = mt5_module if mt5_module is not None else mt5
        self.terminal_path = terminal_path
        self.magic_number = magic_number
        self.login = login
        self.password = password
        self.server = server
        self._connected = False
        self._bound_account_identity: AccountIdentity | None = None

    def connect(self) -> bool:
        """Connect to the explicitly configured MT5 account when supplied.

        MetaQuotes documents initialize(path, login, password, server) as the
        supported way to select a specific account. Supplying an account is
        important for unattended execution because connecting to the terminal's
        last-used account is otherwise ambiguous.
        """
        if self.mt5 is None:
            raise RuntimeError("MetaTrader5 package is not installed.")

        kwargs: dict[str, Any] = {}
        if self.login is not None:
            kwargs["login"] = self.login
        if self.password:
            kwargs["password"] = self.password
        if self.server:
            kwargs["server"] = self.server

        if self.terminal_path:
            ok = self.mt5.initialize(path=self.terminal_path, **kwargs)
        else:
            ok = self.mt5.initialize(**kwargs)
        if not ok:
            err = self.mt5.last_error() if hasattr(self.mt5, "last_error") else "unknown error"
            raise RuntimeError(f"Failed to initialize MT5: {err}")
        self._connected = True
        self._bound_account_identity = None
        return True

    def disconnect(self) -> None:
        if self.mt5 is not None and self._connected:
            self.mt5.shutdown()
            self._connected = False
        self._bound_account_identity = None

    def get_account_identity(self) -> AccountIdentity:
        """Read the broker/account identity and fail closed on missing fields."""
        if not self._connected:
            raise RuntimeError("MT5 executor is not connected.")
        info = self.mt5.account_info()
        if info is None:
            raise RuntimeError(f"MT5 account_info unavailable: {self.mt5.last_error()}")

        login = int(getattr(info, "login", 0))
        server = str(getattr(info, "server", "")).strip()
        company = str(getattr(info, "company", "")).strip()
        trade_mode = int(getattr(info, "trade_mode", -1))
        if login <= 0 or not server or not company or trade_mode < 0:
            raise RuntimeError("MT5 account identity is incomplete; refusing execution")
        return AccountIdentity(login=login, server=server, company=company, trade_mode=trade_mode)

    def bind_account_identity(self, identity: AccountIdentity) -> None:
        """Bind this executor to one verified account identity for its session."""
        current = self.get_account_identity()
        if current != identity:
            raise RuntimeError("cannot bind executor: current MT5 account identity does not match expected identity")
        if self._bound_account_identity is not None and self._bound_account_identity != identity:
            raise RuntimeError("MT5 executor account identity is already bound to a different account")
        self._bound_account_identity = identity

    def _assert_bound_account_identity(self) -> None:
        """Re-check the bound account immediately before any broker execution."""
        if self._bound_account_identity is None:
            raise RuntimeError("MT5 executor account identity is not bound; execution is disabled")
        current = self.get_account_identity()
        if current != self._bound_account_identity:
            raise RuntimeError(
                "MT5 executor account identity changed: "
                f"expected login={self._bound_account_identity.login}, server={self._bound_account_identity.server!r}, "
                f"company={self._bound_account_identity.company!r}, trade_mode={self._bound_account_identity.trade_mode}; "
                f"got login={current.login}, server={current.server!r}, company={current.company!r}, trade_mode={current.trade_mode}"
            )

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
        """Validate, order_check, then submit one market order."""
        if not self._connected:
            return OrderResult(False, -1, error_message="MT5 executor is not connected")
        try:
            self._assert_bound_account_identity()
        except RuntimeError as exc:
            return OrderResult(False, -1, error_message=str(exc))
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
        contract = self.get_symbol_contract(symbol)
        if not self._valid_step_volume(volume, contract.volume_min, contract.volume_max, contract.volume_step):
            return OrderResult(False, -1, error_message="Order volume does not match broker min/max/step")

        tick = self.mt5.symbol_info_tick(symbol)
        if tick is None:
            return OrderResult(False, -1, error_message=f"Could not retrieve current tick for {symbol}")
        bid = float(tick.bid)
        ask = float(tick.ask)
        if not all(isfinite(value) and value > 0 for value in (bid, ask)) or ask < bid:
            return OrderResult(False, -1, error_message="Broker returned an invalid bid/ask")
        price = ask if direction == ORDER_BUY else bid

        if direction == ORDER_BUY and sl >= price:
            return OrderResult(False, -1, error_message="BUY Stop Loss must be below current ask")
        if direction == ORDER_SELL and sl <= price:
            return OrderResult(False, -1, error_message="SELL Stop Loss must be above current bid")
        if tp is not None:
            if direction == ORDER_BUY and tp <= price:
                return OrderResult(False, -1, error_message="BUY Take Profit must be above current ask")
            if direction == ORDER_SELL and tp >= price:
                return OrderResult(False, -1, error_message="SELL Take Profit must be below current bid")

        stops_level = int(getattr(info, "trade_stops_level", 0))
        min_stop_distance = stops_level * contract.point
        if min_stop_distance > 0 and abs(price - sl) < min_stop_distance:
            return OrderResult(False, -1, error_message="Stop Loss is inside broker minimum stop distance")
        if tp is not None and min_stop_distance > 0 and abs(tp - price) < min_stop_distance:
            return OrderResult(False, -1, error_message="Take Profit is inside broker minimum stop distance")

        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": self.mt5.ORDER_TYPE_BUY if direction == ORDER_BUY else self.mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": sl,
            "tp": tp or 0.0,
            "deviation": deviation_points,
            "magic": self.magic_number,
            "comment": comment,
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": _resolve_filling_mode(self.mt5, info),
        }
        check = self.mt5.order_check(request)
        if check is None:
            return OrderResult(False, -1, error_message=f"MT5 order_check returned no result: {self.mt5.last_error()}")
        check_retcode = int(getattr(check, "retcode", -1))
        if check_retcode != 0:
            return OrderResult(False, check_retcode, error_message=f"MT5 order_check rejected order: {getattr(check, 'comment', '')}")

        result = self.mt5.order_send(request)
        if result is None:
            return OrderResult(False, -1, error_message=f"MT5 order_send returned no result: {self.mt5.last_error()}")
        retcode = int(getattr(result, "retcode", -1))
        if retcode != int(getattr(self.mt5, "TRADE_RETCODE_DONE", 10009)):
            return OrderResult(False, retcode, error_message=str(getattr(result, "comment", "MT5 order rejected")))
        return OrderResult(
            True,
            retcode,
            ticket=int(getattr(result, "order", 0) or getattr(result, "deal", 0) or 0),
            price=float(getattr(result, "price", price)),
            volume=float(getattr(result, "volume", volume)),
            comment=str(getattr(result, "comment", "")),
        )

    def get_open_positions(self, symbol: str | None = None) -> list[PositionSnapshot]:
        if not self._connected:
            raise RuntimeError("MT5 executor is not connected.")
        self._assert_bound_account_identity()
        positions = self.mt5.positions_get(symbol=symbol) if symbol else self.mt5.positions_get()
        if positions is None:
            raise RuntimeError(f"MT5 positions_get failed: {self.mt5.last_error()}")
        result: list[PositionSnapshot] = []
        for position in positions:
            if int(getattr(position, "magic", 0)) != self.magic_number:
                continue
            result.append(
                PositionSnapshot(
                    ticket=int(position.ticket),
                    symbol=str(position.symbol),
                    order_type=ORDER_BUY if int(position.type) == int(getattr(self.mt5, "POSITION_TYPE_BUY", 0)) else ORDER_SELL,
                    volume=float(position.volume),
                    open_price=float(position.price_open),
                    sl=float(position.sl),
                    tp=float(position.tp),
                    profit=float(position.profit),
                    magic=int(position.magic),
                    open_time=datetime.fromtimestamp(int(position.time), tz=timezone.utc),
                )
            )
        return result
