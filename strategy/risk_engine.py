"""Portfolio-level risk controls kept separate from the two core setups.

This module does not decide LONG/SHORT entries. It only answers whether a
strategy signal may be sized/opened under explicit account-risk constraints.
All calculations are deterministic and side-effect free.
"""

from dataclasses import dataclass
from math import isfinite


LONG = "LONG"
SHORT = "SHORT"
WAIT = "WAIT"


@dataclass(frozen=True)
class RiskLimits:
    """Hard account-level limits for one trading session."""

    risk_per_trade: float = 0.01
    max_daily_loss: float = 0.03
    max_open_risk: float = 0.02
    max_positions: int = 1
    min_quantity: float = 0.0
    max_quantity: float | None = None

    def __post_init__(self) -> None:
        if not 0.0 < self.risk_per_trade <= 1.0:
            raise ValueError("risk_per_trade must be > 0 and <= 1")
        if not 0.0 < self.max_daily_loss <= 1.0:
            raise ValueError("max_daily_loss must be > 0 and <= 1")
        if not 0.0 < self.max_open_risk <= 1.0:
            raise ValueError("max_open_risk must be > 0 and <= 1")
        if self.max_positions < 1:
            raise ValueError("max_positions must be >= 1")
        if not isfinite(self.min_quantity) or self.min_quantity < 0:
            raise ValueError("min_quantity must be finite and >= 0")
        if self.max_quantity is not None:
            if not isfinite(self.max_quantity) or self.max_quantity <= 0:
                raise ValueError("max_quantity must be finite and > 0")
            if self.max_quantity < self.min_quantity:
                raise ValueError("max_quantity must be >= min_quantity")


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reason: str
    quantity: float = 0.0
    risk_amount: float = 0.0
    risk_fraction: float = 0.0


def position_size(
    equity: float,
    entry: float,
    stop: float,
    risk_fraction: float,
    *,
    value_per_price_unit: float = 1.0,
    quantity_step: float = 0.0,
) -> float:
    """Return quantity sized to lose at most ``risk_fraction`` at the stop.

    ``value_per_price_unit`` converts one price unit of movement for one unit
    of quantity into account currency. Quantity is optionally floored to the
    broker's minimum step; it is never rounded upward because that could exceed
    the requested risk budget.
    """
    for name, value in {
        "equity": equity,
        "entry": entry,
        "stop": stop,
        "risk_fraction": risk_fraction,
        "value_per_price_unit": value_per_price_unit,
    }.items():
        if not isfinite(value):
            raise ValueError(f"{name} must be finite")
    if equity <= 0:
        raise ValueError("equity must be > 0")
    if not 0.0 < risk_fraction <= 1.0:
        raise ValueError("risk_fraction must be > 0 and <= 1")
    if value_per_price_unit <= 0:
        raise ValueError("value_per_price_unit must be > 0")
    if entry == stop:
        raise ValueError("entry and stop must differ")
    if quantity_step < 0 or not isfinite(quantity_step):
        raise ValueError("quantity_step must be finite and >= 0")

    risk_budget = equity * risk_fraction
    risk_per_unit = abs(entry - stop) * value_per_price_unit
    raw_quantity = risk_budget / risk_per_unit
    if quantity_step == 0:
        return raw_quantity
    return (raw_quantity // quantity_step) * quantity_step


def evaluate_risk(
    *,
    equity: float,
    entry: float,
    stop: float,
    limits: RiskLimits,
    daily_realized_loss: float = 0.0,
    open_risk_amount: float = 0.0,
    open_positions: int = 0,
    value_per_price_unit: float = 1.0,
    quantity_step: float = 0.0,
) -> RiskDecision:
    """Apply hard risk limits without modifying the underlying strategy signal."""
    values = {
        "equity": equity,
        "entry": entry,
        "stop": stop,
        "daily_realized_loss": daily_realized_loss,
        "open_risk_amount": open_risk_amount,
    }
    for name, value in values.items():
        if not isfinite(value):
            raise ValueError(f"{name} must be finite")
    if equity <= 0:
        raise ValueError("equity must be > 0")
    if daily_realized_loss < 0:
        raise ValueError("daily_realized_loss must be >= 0")
    if open_risk_amount < 0:
        raise ValueError("open_risk_amount must be >= 0")
    if open_positions < 0:
        raise ValueError("open_positions must be >= 0")

    daily_limit = equity * limits.max_daily_loss
    if daily_realized_loss >= daily_limit:
        return RiskDecision(False, "daily loss limit reached")
    if open_positions >= limits.max_positions:
        return RiskDecision(False, "maximum open positions reached")

    remaining_open_risk = equity * limits.max_open_risk - open_risk_amount
    if remaining_open_risk <= 0:
        return RiskDecision(False, "maximum open risk reached")

    requested_risk = min(equity * limits.risk_per_trade, remaining_open_risk)
    risk_fraction = requested_risk / equity
    quantity = position_size(
        equity,
        entry,
        stop,
        risk_fraction,
        value_per_price_unit=value_per_price_unit,
        quantity_step=quantity_step,
    )
    if quantity <= 0:
        return RiskDecision(False, "computed quantity is below broker minimum step")

    if limits.min_quantity > 0 and quantity < limits.min_quantity:
        return RiskDecision(False, "computed quantity is below configured minimum quantity")

    if limits.max_quantity is not None and quantity > limits.max_quantity:
        quantity = limits.max_quantity
        if quantity_step > 0:
            quantity = (quantity // quantity_step) * quantity_step
        if quantity <= 0:
            return RiskDecision(False, "maximum quantity cap is below broker minimum step")
        if limits.min_quantity > 0 and quantity < limits.min_quantity:
            return RiskDecision(False, "quantity cap leaves less than configured minimum quantity")

    risk_amount = abs(entry - stop) * value_per_price_unit * quantity
    if risk_amount > requested_risk * (1.0 + 1e-12):
        return RiskDecision(False, "sizing exceeded the configured risk budget")

    return RiskDecision(True, "risk checks passed", quantity, risk_amount, risk_amount / equity)
