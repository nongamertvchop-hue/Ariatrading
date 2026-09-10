from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from strategy.broker_contract import SymbolContract


class MT5Gateway:
    """MT5 account/data gateway with no implicit LIVE order submission."""

    def __init__(self, *, terminal_path: str = "", login: int | None = None, password: str = "", server: str = "", magic_number: int = 8808, mt5_module: Any | None = None) -> None:
        if mt5_module is None:
            try:
                import MetaTrader5 as mt5_module  # type: ignore
            except ImportError as exc:
                raise RuntimeError("MetaTrader5 package is required for MT5Gateway") from exc
        self.mt5 = mt5_module
        self.magic_number = int(magic_number)
        kwargs: dict[str, Any] = {}
        if login is not None:
            kwargs["login"] = int(login)
            kwargs["password"] = password
            kwargs["server"] = server
        ok = self.mt5.initialize(path=terminal_path, **kwargs) if terminal_path else self.mt5.initialize(**kwargs)
        if not ok:
            raise RuntimeError(f"MT5 initialize failed: {self.mt5.last_error()}")

    def shutdown(self) -> None:
        self.mt5.shutdown()

    def account(self) -> dict[str, Any]:
        info = self.mt5.account_info()
        if info is None:
            raise RuntimeError(f"MT5 account_info failed: {self.mt5.last_error()}")
        return {"login": int(info.login), "server": str(info.server), "balance": float(info.balance), "equity": float(info.equity), "margin_free": float(info.margin_free), "trade_allowed": bool(info.trade_allowed)}

    def symbol_contract(self, symbol: str) -> SymbolContract:
        info = self.mt5.symbol_info(symbol)
        if info is None:
            raise RuntimeError(f"unknown MT5 symbol: {symbol}")
        return SymbolContract(symbol=symbol, digits=int(info.digits), point=float(info.point), volume_min=float(info.volume_min), volume_max=float(info.volume_max), volume_step=float(info.volume_step))

    def tick(self, symbol: str) -> dict[str, Any]:
        tick = self.mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"MT5 symbol_info_tick failed: {self.mt5.last_error()}")
        ts = datetime.fromtimestamp(int(tick.time), tz=timezone.utc)
        return {"time": ts, "bid": float(tick.bid), "ask": float(tick.ask), "last": float(tick.last), "spread": float(tick.ask - tick.bid)}

    def positions(self, symbol: str | None = None) -> list[dict[str, Any]]:
        rows = self.mt5.positions_get(symbol=symbol) if symbol else self.mt5.positions_get()
        if rows is None:
            raise RuntimeError(f"MT5 positions_get failed: {self.mt5.last_error()}")
        return [{"ticket": int(p.ticket), "symbol": str(p.symbol), "type": int(p.type), "volume": float(p.volume), "price_open": float(p.price_open), "sl": float(p.sl), "tp": float(p.tp), "magic": int(p.magic), "time": datetime.fromtimestamp(int(p.time), tz=timezone.utc)} for p in rows]

    def order_preflight(self, request: dict[str, Any]) -> Any:
        """Run broker-side order_check only; intentionally no order_send here."""
        required = {"action", "symbol", "volume", "type", "price"}
        missing = required - request.keys()
        if missing:
            raise ValueError(f"missing MT5 order_check fields: {sorted(missing)}")
        return self.mt5.order_check(request)

    def send_order(self, request: dict[str, Any]) -> Any:
        raise RuntimeError("MT5 live order_send is disabled in the current Ariatrading release boundary")
