"""Conservative historical execution-cost simulation.

This module sits below the strategy/risk layers. It models execution frictions
for research only: spread, fixed price-unit commission, slippage, bar-based
latency, optional session filtering, and price precision. It never connects to
a broker or submits orders.
"""

from dataclasses import dataclass
from datetime import time

from .risk import LOSS, OPEN, WIN, RiskPlan, TradeResult


@dataclass(frozen=True)
class ExecutionModel:
    spread: float = 0.0
    slippage: float = 0.0
    commission: float = 0.0
    latency_bars: int = 0
    price_digits: int | None = None
    session_start: time | None = None
    session_end: time | None = None

    def __post_init__(self) -> None:
        if self.spread < 0 or self.slippage < 0 or self.commission < 0:
            raise ValueError("spread, slippage and commission must be >= 0")
        if self.latency_bars < 0:
            raise ValueError("latency_bars must be >= 0")
        if self.price_digits is not None and self.price_digits < 0:
            raise ValueError("price_digits must be >= 0")
        if (self.session_start is None) != (self.session_end is None):
            raise ValueError("session_start and session_end must be supplied together")


def _round(value: float, digits: int | None) -> float:
    return round(value, digits) if digits is not None else value


def _in_session(raw: dict, model: ExecutionModel) -> bool:
    if model.session_start is None:
        return True
    timestamp = raw.get("time")
    if timestamp is None:
        raise ValueError("session filtering requires candle time")
    current = timestamp.timetz().replace(tzinfo=None)
    if model.session_start <= model.session_end:
        return model.session_start <= current <= model.session_end
    return current >= model.session_start or current <= model.session_end


def simulate_realistic_exit(
    plan: RiskPlan,
    future_candles: list[dict],
    model: ExecutionModel,
    max_bars: int | None = None,
) -> TradeResult:
    """Simulate exits after explicit execution frictions are applied.

    The simulator keeps the strategy's original stop/target levels. Spread,
    slippage and commission affect realized entry/exit economics; latency skips
    the first configured number of future bars. If both stop and target are
    reachable in one candle, the stop remains the conservative first event.
    """
    if max_bars is not None and max_bars < 1:
        raise ValueError("max_bars must be >= 1")

    sample = future_candles if max_bars is None else future_candles[:max_bars]
    if model.latency_bars >= len(sample):
        return TradeResult(plan.direction, plan.entry, plan.stop, plan.target, None, OPEN, len(sample), 0.0)

    risk = plan.risk_distance
    if risk <= 0:
        raise ValueError("risk distance must be > 0")

    effective_entry = (
        plan.entry + model.spread / 2 + model.slippage
        if plan.direction == "LONG"
        else plan.entry - model.spread / 2 - model.slippage
    )
    effective_entry = _round(effective_entry, model.price_digits)

    for i, raw in enumerate(sample[model.latency_bars:], start=model.latency_bars + 1):
        if not _in_session(raw, model):
            continue
        high = float(raw["high"])
        low = float(raw["low"])
        if high < low:
            raise ValueError("candle high must be >= low")

        if plan.direction == "LONG":
            bid_high = _round(high - model.spread / 2 - model.slippage, model.price_digits)
            bid_low = _round(low - model.spread / 2 - model.slippage, model.price_digits)
            if bid_low <= plan.stop:
                exit_price = _round(plan.stop, model.price_digits)
                pnl = (exit_price - effective_entry) - model.commission
                return TradeResult("LONG", effective_entry, plan.stop, plan.target, exit_price, LOSS, i, pnl / risk)
            if bid_high >= plan.target:
                exit_price = _round(plan.target, model.price_digits)
                pnl = (exit_price - effective_entry) - model.commission
                return TradeResult("LONG", effective_entry, plan.stop, plan.target, exit_price, WIN, i, pnl / risk)
        else:
            ask_high = _round(high + model.spread / 2 + model.slippage, model.price_digits)
            ask_low = _round(low + model.spread / 2 + model.slippage, model.price_digits)
            if ask_high >= plan.stop:
                exit_price = _round(plan.stop, model.price_digits)
                pnl = (effective_entry - exit_price) - model.commission
                return TradeResult("SHORT", effective_entry, plan.stop, plan.target, exit_price, LOSS, i, pnl / risk)
            if ask_low <= plan.target:
                exit_price = _round(plan.target, model.price_digits)
                pnl = (effective_entry - exit_price) - model.commission
                return TradeResult("SHORT", effective_entry, plan.stop, plan.target, exit_price, WIN, i, pnl / risk)

    return TradeResult(plan.direction, effective_entry, plan.stop, plan.target, None, OPEN, len(sample), 0.0)
