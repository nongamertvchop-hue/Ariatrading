"""Translate a confirmed price-action signal into a risk-checked trade plan.

This module is deliberately the boundary between strategy and sizing:
strategy decides LONG/SHORT and the protective stop; risk controls decide
whether that signal may be sized. No broker or order side effects occur here.
"""

from dataclasses import dataclass
from math import isfinite

from .engine import EngineSignal, LONG, SHORT
from .risk_engine import RiskDecision, RiskLimits, evaluate_risk


@dataclass(frozen=True)
class TradePlan:
    """Immutable, risk-checked plan ready for a separate execution layer."""

    action: str
    entry: float
    stop: float
    risk: RiskDecision


def build_trade_plan(
    signal: EngineSignal,
    *,
    equity: float,
    limits: RiskLimits,
    daily_realized_loss: float = 0.0,
    open_risk_amount: float = 0.0,
    open_positions: int = 0,
    value_per_price_unit: float = 1.0,
    quantity_step: float = 0.0,
) -> TradePlan:
    """Build a plan only from an actionable signal with a valid protective stop."""
    if signal.action not in {LONG, SHORT}:
        raise ValueError("only LONG or SHORT signals can become trade plans")
    if signal.entry_reference is None or signal.stop_reference is None:
        raise ValueError("actionable signal must contain entry and stop references")

    entry = float(signal.entry_reference)
    stop = float(signal.stop_reference)
    if not isfinite(entry) or not isfinite(stop):
        raise ValueError("entry and stop must be finite")

    if signal.action == LONG and stop >= entry:
        raise ValueError("LONG protective stop must be below entry")
    if signal.action == SHORT and stop <= entry:
        raise ValueError("SHORT protective stop must be above entry")

    risk = evaluate_risk(
        equity=equity,
        entry=entry,
        stop=stop,
        limits=limits,
        daily_realized_loss=daily_realized_loss,
        open_risk_amount=open_risk_amount,
        open_positions=open_positions,
        value_per_price_unit=value_per_price_unit,
        quantity_step=quantity_step,
    )
    return TradePlan(signal.action, entry, stop, risk)
