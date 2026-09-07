"""MetaTrader 5 demo-account execution adapter.

This module is intentionally the only runtime component in Ariatrading that
may call ``order_send``. It refuses to operate unless the connected MT5
account explicitly reports ``ACCOUNT_TRADE_MODE_DEMO``.

The strategy layer remains broker-agnostic. Callers provide a fully validated
signal/position plan and this adapter performs only the broker-specific
contract checks and execution steps.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from math import isfinite
from typing import Any

LONG = "LONG"
SHORT = "SHORT"


class DemoExecutionError(RuntimeError):
    """Raised when demo execution cannot proceed safely."""


@dataclass(frozen=True)
class DemoOrderResult:
    client_order_id: str
    symbol: str
    direction: str
    requested_volume: float
    filled_volume: float
    average_price: float | None
    status: str
    broker_order_id: str | None
    broker_deal_id: str | None
    retcode: int
    comment: str
    timestamp: datetime


class MT5DemoExecutionAdapter:
    """Fail-closed market execution adapter restricted to MT5 demo accounts."""

    def __init__(
        self,
        mt5_module: Any,
        *,
        magic: int = 26090701,
        deviation_points: int = 20,
        max_volume: float = 0.10,
        comment_prefix: str = "ARIA-DEMO",
    ) -> None:
        self.mt5 = mt5_module
        self.magic = int(magic)
        self.deviation_points = int(deviation_points)
        self.max_volume = float(max_volume)
        self.comment_prefix = comment_prefix
        if self.magic <= 0:
            raise ValueError("magic must be > 0")
        if self.deviation_points < 0:
            raise ValueError("deviation_points must be >= 0")
        if not isfinite(self.max_volume) or self.max_volume <= 0:
            raise ValueError("max_volume must be finite and > 0")
        if not comment_prefix:
            raise ValueError("comment_prefix must not be empty")

    def connect(self, *, terminal_path: str | None = None) -> None:
        """Initialize MT5 and hard-stop unless the account is a demo account."""
        initialized = (
            self.mt5.initialize(path=terminal_path)
            if terminal_path
            else self.mt5.initialize()
        )
        if not initialized:
            raise DemoExecutionError(f"MT5 initialize failed: {self.mt5.last_error()}")
        try:
            self._assert_demo_account()
        except Exception:
            self.mt5.shutdown()
            raise

    def close(self) -> None:
        self.mt5.shutdown()

    def account_snapshot(self) -> dict[str, Any]:
        """Return a sanitized account snapshot useful for runtime monitoring."""
        self._assert_demo_account()
        account = self.mt5.account_info()
        if account is None:
            raise DemoExecutionError(f"MT5 account_info failed: {self.mt5.last_error()}")
        return {
            "login": int(account.login),
            "server": str(account.server),
            "company": str(account.company),
            "trade_mode": int(account.trade_mode),
            "trade_allowed": bool(account.trade_allowed),
            "trade_expert": bool(account.trade_expert),
            "currency": str(account.currency),
            "balance": float(account.balance),
            "equity": float(account.equity),
            "margin_free": float(account.margin_free),
        }

    def positions(self, symbol: str | None = None) -> tuple[Any, ...]:
        """Return only ARIA-managed demo positions identified by ``magic``."""
        self._assert_demo_account()
        positions = self.mt5.positions_get(symbol=symbol) if symbol else self.mt5.positions_get()
        if positions is None:
            error = self.mt5.last_error()
            raise DemoExecutionError(f"MT5 positions_get failed: {error}")
        return tuple(position for position in positions if int(position.magic) == self.magic)

    def open_market(
        self,
        *,
        client_order_id: str,
        symbol: str,
        direction: str,
        volume: float,
        stop_loss: float,
        take_profit: float,
    ) -> DemoOrderResult:
        """Open one protected market position on the connected demo account."""
        self._assert_demo_account()
        self._validate_direction(direction)
        if not client_order_id:
            raise ValueError("client_order_id must not be empty")
        if not symbol:
            raise ValueError("symbol must not be empty")
        if not isfinite(volume) or volume <= 0:
            raise ValueError("volume must be finite and > 0")
        if volume > self.max_volume:
            raise DemoExecutionError(
                f"requested volume {volume} exceeds hard demo max_volume {self.max_volume}"
            )
        if not isfinite(stop_loss) or stop_loss <= 0:
            raise ValueError("stop_loss must be finite and > 0")
        if not isfinite(take_profit) or take_profit <= 0:
            raise ValueError("take_profit must be finite and > 0")

        managed_positions = self.positions(symbol)
        if managed_positions:
            raise DemoExecutionError(
                f"managed demo position already exists for {symbol}; refusing duplicate entry"
            )

        info = self._symbol_info(symbol)
        volume = self._normalize_volume(volume, info)
        tick = self.mt5.symbol_info_tick(symbol)
        if tick is None:
            raise DemoExecutionError(f"MT5 tick request failed: {self.mt5.last_error()}")

        digits = int(info.digits)
        price = round(float(tick.ask if direction == LONG else tick.bid), digits)
        stop_loss = round(float(stop_loss), digits)
        take_profit = round(float(take_profit), digits)

        if direction == LONG and not (stop_loss < price < take_profit):
            raise DemoExecutionError("LONG requires stop_loss < current ask < take_profit")
        if direction == SHORT and not (take_profit < price < stop_loss):
            raise DemoExecutionError("SHORT requires take_profit < current bid < stop_loss")

        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": self.mt5.ORDER_TYPE_BUY if direction == LONG else self.mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": stop_loss,
            "tp": take_profit,
            "deviation": self.deviation_points,
            "magic": self.magic,
            "comment": f"{self.comment_prefix}:{client_order_id}",
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": self._select_filling_mode(info),
        }

        check = self.mt5.order_check(request)
        self._assert_check_ok(check)

        result = self.mt5.order_send(request)
        if result is None:
            raise DemoExecutionError(f"MT5 order_send returned None: {self.mt5.last_error()}")
        retcode = int(result.retcode)
        success_codes = {
            int(self.mt5.TRADE_RETCODE_DONE),
            int(self.mt5.TRADE_RETCODE_DONE_PARTIAL),
        }
        status = "FILLED" if retcode == int(self.mt5.TRADE_RETCODE_DONE) else "PARTIALLY_FILLED"
        if retcode not in success_codes:
            raise DemoExecutionError(
                f"demo order rejected: retcode={retcode}, comment={getattr(result, 'comment', '')}"
            )

        return DemoOrderResult(
            client_order_id=client_order_id,
            symbol=symbol,
            direction=direction,
            requested_volume=volume,
            filled_volume=float(getattr(result, "volume", 0.0) or 0.0),
            average_price=float(getattr(result, "price", price) or price),
            status=status,
            broker_order_id=str(getattr(result, "order", "") or "") or None,
            broker_deal_id=str(getattr(result, "deal", "") or "") or None,
            retcode=retcode,
            comment=str(getattr(result, "comment", "")),
            timestamp=datetime.now(timezone.utc),
        )

    def close_position(self, ticket: int, *, client_order_id: str) -> DemoOrderResult:
        """Close one ARIA-managed demo position by ticket."""
        self._assert_demo_account()
        if ticket <= 0:
            raise ValueError("ticket must be > 0")
        if not client_order_id:
            raise ValueError("client_order_id must not be empty")

        positions = self.mt5.positions_get(ticket=ticket)
        if positions is None:
            raise DemoExecutionError(f"MT5 position lookup failed: {self.mt5.last_error()}")
        if len(positions) != 1:
            raise DemoExecutionError(f"expected exactly one position for ticket {ticket}")
        position = positions[0]
        if int(position.magic) != self.magic:
            raise DemoExecutionError("refusing to close a position not owned by Ariatrading")

        symbol = str(position.symbol)
        info = self._symbol_info(symbol)
        tick = self.mt5.symbol_info_tick(symbol)
        if tick is None:
            raise DemoExecutionError(f"MT5 tick request failed: {self.mt5.last_error()}")
        digits = int(info.digits)
        direction = SHORT if int(position.type) == int(self.mt5.POSITION_TYPE_BUY) else LONG
        price = round(float(tick.bid if direction == SHORT else tick.ask), digits)
        volume = self._normalize_volume(float(position.volume), info)

        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": self.mt5.ORDER_TYPE_SELL if direction == SHORT else self.mt5.ORDER_TYPE_BUY,
            "position": int(position.ticket),
            "price": price,
            "deviation": self.deviation_points,
            "magic": self.magic,
            "comment": f"{self.comment_prefix}:CLOSE:{client_order_id}",
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": self._select_filling_mode(info),
        }

        check = self.mt5.order_check(request)
        self._assert_check_ok(check)
        result = self.mt5.order_send(request)
        if result is None:
            raise DemoExecutionError(f"MT5 close order_send returned None: {self.mt5.last_error()}")

        retcode = int(result.retcode)
        if retcode not in {
            int(self.mt5.TRADE_RETCODE_DONE),
            int(self.mt5.TRADE_RETCODE_DONE_PARTIAL),
        }:
            raise DemoExecutionError(
                f"demo close rejected: retcode={retcode}, comment={getattr(result, 'comment', '')}"
            )
        status = "FILLED" if retcode == int(self.mt5.TRADE_RETCODE_DONE) else "PARTIALLY_FILLED"
        return DemoOrderResult(
            client_order_id=client_order_id,
            symbol=symbol,
            direction=direction,
            requested_volume=volume,
            filled_volume=float(getattr(result, "volume", 0.0) or 0.0),
            average_price=float(getattr(result, "price", price) or price),
            status=status,
            broker_order_id=str(getattr(result, "order", "") or "") or None,
            broker_deal_id=str(getattr(result, "deal", "") or "") or None,
            retcode=retcode,
            comment=str(getattr(result, "comment", "")),
            timestamp=datetime.now(timezone.utc),
        )

    def _assert_demo_account(self) -> None:
        account = self.mt5.account_info()
        if account is None:
            raise DemoExecutionError(f"MT5 account_info failed: {self.mt5.last_error()}")
        demo_mode = int(self.mt5.ACCOUNT_TRADE_MODE_DEMO)
        if int(account.trade_mode) != demo_mode:
            raise DemoExecutionError(
                "DEMO-ONLY guard: connected MT5 account is not a demo account"
            )
        if not bool(account.trade_allowed):
            raise DemoExecutionError("MT5 account trade_allowed is false")
        if not bool(account.trade_expert):
            raise DemoExecutionError("MT5 account trade_expert is false")
        terminal = self.mt5.terminal_info()
        if terminal is None:
            raise DemoExecutionError(f"MT5 terminal_info failed: {self.mt5.last_error()}")
        if hasattr(terminal, "trade_allowed") and not bool(terminal.trade_allowed):
            raise DemoExecutionError("MT5 terminal trading is disabled")

    def _symbol_info(self, symbol: str) -> Any:
        info = self.mt5.symbol_info(symbol)
        if info is None:
            raise DemoExecutionError(f"symbol not found: {symbol}")
        if not bool(info.visible) and not self.mt5.symbol_select(symbol, True):
            raise DemoExecutionError(f"symbol unavailable in MarketWatch: {symbol}")
        return info

    @staticmethod
    def _validate_direction(direction: str) -> None:
        if direction not in {LONG, SHORT}:
            raise ValueError("direction must be LONG or SHORT")

    def _normalize_volume(self, volume: float, info: Any) -> float:
        minimum = float(info.volume_min)
        maximum = min(float(info.volume_max), self.max_volume)
        step = float(info.volume_step)
        if step <= 0:
            raise DemoExecutionError("broker returned an invalid volume_step")
        if volume < minimum:
            volume = minimum
        if volume > maximum:
            raise DemoExecutionError(
                f"volume {volume} exceeds broker/demo maximum {maximum}"
            )
        quantized = (
            Decimal(str(volume)) / Decimal(str(step))
        ).to_integral_value(rounding=ROUND_DOWN) * Decimal(str(step))
        normalized = float(quantized)
        if normalized < minimum or normalized <= 0:
            raise DemoExecutionError("normalized volume is below broker minimum")
        return normalized

    def _select_filling_mode(self, info: Any) -> int:
        allowed = int(getattr(info, "filling_mode", 0))
        market_execution = int(getattr(self.mt5, "SYMBOL_TRADE_EXECUTION_MARKET", 2))
        if int(getattr(info, "trade_exemode", -1)) != market_execution:
            return int(self.mt5.ORDER_FILLING_RETURN)

        for flag, order_mode in (
            (int(getattr(self.mt5, "SYMBOL_FILLING_IOC", 2)), int(self.mt5.ORDER_FILLING_IOC)),
            (int(getattr(self.mt5, "SYMBOL_FILLING_FOK", 1)), int(self.mt5.ORDER_FILLING_FOK)),
        ):
            if allowed & flag == flag:
                return order_mode
        raise DemoExecutionError("broker does not advertise a supported market filling mode")

    def _assert_check_ok(self, check: Any) -> None:
        if check is None:
            raise DemoExecutionError(f"MT5 order_check returned None: {self.mt5.last_error()}")
        retcode = int(getattr(check, "retcode", -1))
        if retcode != 0:
            raise DemoExecutionError(
                f"demo order_check rejected request: retcode={retcode}, "
                f"comment={getattr(check, 'comment', '')}"
            )


__all__ = ["DemoExecutionError", "DemoOrderResult", "MT5DemoExecutionAdapter", "LONG", "SHORT"]
