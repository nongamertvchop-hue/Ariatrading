"""Portfolio exposure and stop-defined cash-risk calculations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from live.mt5_executor import PositionSnapshot
from strategy.forex_risk import ForexSymbolContract


@dataclass(frozen=True)
class ExposureSummary:
    total_positions: int
    by_symbol: dict[str, int]
    by_direction: dict[str, float]
    risk_cash: float


def estimate_position_risk_cash(position: PositionSnapshot, contract: ForexSymbolContract) -> float:
    """Estimate loss at the stored SL using broker tick value/tick size."""
    if position.volume <= 0 or position.sl <= 0 or position.open_price <= 0:
        return 0.0
    if not all(math.isfinite(value) for value in (position.volume, position.sl, position.open_price, contract.trade_tick_value, contract.trade_tick_size)):
        raise ValueError("non-finite position or contract risk input")
    if contract.trade_tick_value <= 0 or contract.trade_tick_size <= 0:
        return 0.0
    distance = abs(position.open_price - position.sl)
    return distance / contract.trade_tick_size * contract.trade_tick_value * position.volume


def summarize_exposure(
    positions: Iterable[PositionSnapshot],
    contracts: dict[str, ForexSymbolContract],
) -> ExposureSummary:
    by_symbol: dict[str, int] = {}
    by_direction: dict[str, float] = {"BUY": 0.0, "SELL": 0.0}
    risk_cash = 0.0
    total = 0
    for position in positions:
        symbol = position.symbol.upper()
        direction = position.order_type.upper()
        if direction not in by_direction:
            raise ValueError(f"unsupported position direction: {position.order_type}")
        total += 1
        by_symbol[symbol] = by_symbol.get(symbol, 0) + 1
        by_direction[direction] += float(position.volume)
        contract = contracts.get(symbol)
        if contract is not None:
            risk_cash += estimate_position_risk_cash(position, contract)
    if not math.isfinite(risk_cash) or risk_cash < 0:
        raise ValueError("aggregate risk must be finite and non-negative")
    return ExposureSummary(total, by_symbol, by_direction, risk_cash)


def risk_budget_allows(*, current_risk_cash: float, candidate_risk_cash: float, equity: float, max_fraction: float) -> tuple[bool, str]:
    """Fail closed when existing + candidate stop risk exceeds the portfolio budget."""
    values = (current_risk_cash, candidate_risk_cash, equity, max_fraction)
    if not all(math.isfinite(value) for value in values):
        return False, "risk budget input is non-finite"
    if equity <= 0 or current_risk_cash < 0 or candidate_risk_cash < 0 or not 0 < max_fraction < 1:
        return False, "risk budget input is invalid"
    budget = equity * max_fraction
    projected = current_risk_cash + candidate_risk_cash
    if projected > budget:
        return False, f"portfolio stop-risk budget exceeded: {projected:.2f} > {budget:.2f}"
    return True, "portfolio stop-risk budget within limit"
