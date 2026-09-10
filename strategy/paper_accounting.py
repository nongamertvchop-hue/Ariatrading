"""Deterministic paper-account accounting.

The engine is deliberately broker-free. It tracks realized/unrealized P/L,
equity peaks, drawdown and trade statistics for paper/demo research only.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

LONG = "LONG"
SHORT = "SHORT"


@dataclass(frozen=True)
class PaperPosition:
    symbol: str
    side: str
    quantity: float
    entry_price: float
    entry_bar_time: str
    contract_multiplier: float = 1.0


@dataclass(frozen=True)
class PaperTrade:
    symbol: str
    side: str
    quantity: float
    entry_price: float
    exit_price: float
    gross_pnl: float
    fees: float
    net_pnl: float
    bars_held: int
    entry_bar_time: str
    exit_bar_time: str


@dataclass(frozen=True)
class AccountSnapshot:
    balance: float
    equity: float
    realized_pnl: float
    unrealized_pnl: float
    peak_equity: float
    drawdown: float
    drawdown_pct: float
    trade_count: int
    win_count: int
    loss_count: int
    flat_count: int


class PaperAccounting:
    """Single-position, deterministic mark-to-market paper account."""

    def __init__(self, *, initial_balance: float = 10_000.0, fee_per_unit: float = 0.0) -> None:
        if not isfinite(initial_balance) or initial_balance <= 0:
            raise ValueError("initial_balance must be finite and > 0")
        if not isfinite(fee_per_unit) or fee_per_unit < 0:
            raise ValueError("fee_per_unit must be finite and >= 0")
        self.initial_balance = float(initial_balance)
        self.fee_per_unit = float(fee_per_unit)
        self.balance = float(initial_balance)
        self.realized_pnl = 0.0
        self.peak_equity = float(initial_balance)
        self.position: PaperPosition | None = None
        self.trades: list[PaperTrade] = []
        self._last_bar_time: str | None = None
        self._bars_held = 0
        self._mark_price: float | None = None

    def open_position(self, *, symbol: str, side: str, quantity: float, entry_price: float, bar_time: str, contract_multiplier: float = 1.0) -> PaperPosition:
        self._validate_side(side)
        self._validate_positive(quantity, "quantity")
        self._validate_positive(entry_price, "entry_price")
        self._validate_positive(contract_multiplier, "contract_multiplier")
        if not bar_time:
            raise ValueError("bar_time must not be empty")
        if self.position is not None:
            raise RuntimeError("paper account already has an open position")
        self.position = PaperPosition(symbol, side, float(quantity), float(entry_price), bar_time, float(contract_multiplier))
        self._last_bar_time = bar_time
        self._bars_held = 0
        self._mark_price = float(entry_price)
        self._refresh_peak()
        return self.position

    def mark(self, *, price: float, bar_time: str | None = None) -> AccountSnapshot:
        self._validate_positive(price, "price")
        if bar_time is not None:
            if self._last_bar_time is not None and bar_time == self._last_bar_time:
                return self.snapshot(mark_price=price)
            if self._last_bar_time is not None and bar_time < self._last_bar_time:
                raise ValueError("bar_time must be monotonic")
            if self.position is not None:
                self._bars_held += 1
            self._last_bar_time = bar_time
        self._mark_price = float(price)
        snapshot = self.snapshot()
        self._refresh_peak(snapshot.equity)
        return self.snapshot()

    def close_position(self, *, exit_price: float, bar_time: str, fee_units: float | None = None) -> PaperTrade:
        self._validate_positive(exit_price, "exit_price")
        if self.position is None:
            raise RuntimeError("paper account is already flat")
        if not bar_time:
            raise ValueError("bar_time must not be empty")
        if self._last_bar_time is not None and bar_time < self._last_bar_time:
            raise ValueError("bar_time must be monotonic")
        position = self.position
        sign = 1.0 if position.side == LONG else -1.0
        gross = (float(exit_price) - position.entry_price) * sign * position.quantity * position.contract_multiplier
        units = position.quantity if fee_units is None else float(fee_units)
        if units < 0 or not isfinite(units):
            raise ValueError("fee_units must be finite and >= 0")
        fees = units * self.fee_per_unit
        net = gross - fees
        self.balance += net
        self.realized_pnl += net
        trade = PaperTrade(position.symbol, position.side, position.quantity, position.entry_price, float(exit_price), gross, fees, net, self._bars_held, position.entry_bar_time, bar_time)
        self.trades.append(trade)
        self.position = None
        self._last_bar_time = bar_time
        self._bars_held = 0
        self._mark_price = float(exit_price)
        self._refresh_peak()
        return trade

    def snapshot(self, *, mark_price: float | None = None) -> AccountSnapshot:
        price = self._mark_price if mark_price is None else float(mark_price)
        unrealized = 0.0
        if self.position is not None and price is not None:
            sign = 1.0 if self.position.side == LONG else -1.0
            unrealized = (price - self.position.entry_price) * sign * self.position.quantity * self.position.contract_multiplier
        equity = self.balance + unrealized
        drawdown = max(0.0, self.peak_equity - equity)
        drawdown_pct = (drawdown / self.peak_equity * 100.0) if self.peak_equity > 0 else 0.0
        wins = sum(1 for trade in self.trades if trade.net_pnl > 0)
        losses = sum(1 for trade in self.trades if trade.net_pnl < 0)
        flats = len(self.trades) - wins - losses
        return AccountSnapshot(self.balance, equity, self.realized_pnl, unrealized, self.peak_equity, drawdown, drawdown_pct, len(self.trades), wins, losses, flats)

    def export_state(self) -> dict:
        return {
            "version": 1,
            "initial_balance": self.initial_balance,
            "fee_per_unit": self.fee_per_unit,
            "balance": self.balance,
            "realized_pnl": self.realized_pnl,
            "peak_equity": self.peak_equity,
            "position": None if self.position is None else self.position.__dict__,
            "trades": [trade.__dict__ for trade in self.trades],
            "last_bar_time": self._last_bar_time,
            "bars_held": self._bars_held,
            "mark_price": self._mark_price,
        }

    @classmethod
    def from_state(cls, payload: dict) -> "PaperAccounting":
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise ValueError("unsupported accounting checkpoint")
        account = cls(initial_balance=float(payload["initial_balance"]), fee_per_unit=float(payload.get("fee_per_unit", 0.0)))
        account.balance = float(payload["balance"])
        account.realized_pnl = float(payload["realized_pnl"])
        account.peak_equity = float(payload["peak_equity"])
        raw_position = payload.get("position")
        if raw_position is not None:
            if not isinstance(raw_position, dict):
                raise ValueError("invalid position checkpoint")
            account._validate_side(str(raw_position["side"]))
            account._validate_positive(float(raw_position["quantity"]), "position quantity")
            account._validate_positive(float(raw_position["entry_price"]), "position entry price")
            account._validate_positive(float(raw_position.get("contract_multiplier", 1.0)), "contract multiplier")
            account.position = PaperPosition(**raw_position)
        raw_trades = payload.get("trades", [])
        if not isinstance(raw_trades, list):
            raise ValueError("invalid trade checkpoint")
        account.trades = []
        for item in raw_trades:
            if not isinstance(item, dict):
                raise ValueError("invalid trade record")
            account._validate_side(str(item["side"]))
            account._validate_positive(float(item["quantity"]), "trade quantity")
            for field in ("entry_price", "exit_price", "gross_pnl", "fees", "net_pnl"):
                if not isfinite(float(item[field])):
                    raise ValueError(f"invalid trade {field}")
            if int(item["bars_held"]) < 0:
                raise ValueError("invalid trade bars_held")
            account.trades.append(PaperTrade(**item))
        account._last_bar_time = payload.get("last_bar_time")
        account._bars_held = int(payload.get("bars_held", 0))
        mark_price = payload.get("mark_price")
        account._mark_price = None if mark_price is None else float(mark_price)
        if not isfinite(account.balance) or not isfinite(account.realized_pnl) or not isfinite(account.peak_equity):
            raise ValueError("accounting checkpoint contains non-finite state")
        if account.balance <= 0 or account.peak_equity <= 0 or account._bars_held < 0:
            raise ValueError("invalid accounting checkpoint values")
        if account._mark_price is not None and not isfinite(account._mark_price):
            raise ValueError("invalid accounting mark price")
        expected_realized = sum(trade.net_pnl for trade in account.trades)
        if abs(expected_realized - account.realized_pnl) > 1e-9:
            raise ValueError("realized P/L does not match trade ledger")
        account._refresh_peak(account.snapshot().equity)
        return account

    def _refresh_peak(self, equity: float | None = None) -> None:
        current = self.snapshot().equity if equity is None else float(equity)
        if current > self.peak_equity:
            self.peak_equity = current

    @staticmethod
    def _validate_side(side: str) -> None:
        if side not in {LONG, SHORT}:
            raise ValueError("side must be LONG or SHORT")

    @staticmethod
    def _validate_positive(value: float, name: str) -> None:
        if not isfinite(float(value)) or float(value) <= 0:
            raise ValueError(f"{name} must be finite and > 0")


__all__ = ["LONG", "SHORT", "PaperPosition", "PaperTrade", "AccountSnapshot", "PaperAccounting"]
