"""Hard safety gate before a strategy signal reaches execution.

This module deliberately does not generate, modify, or score trading setups.
It only combines independent safety decisions: strategy state, data quality,
portfolio risk, position availability, and finite positive order inputs.
Any missing or contradictory safety condition becomes a deny decision.
"""

from dataclasses import dataclass
from math import isfinite

from .engine import EngineSignal, LONG, SHORT, WAIT
from .portfolio_risk import HALT, PortfolioRiskDecision
from .risk_engine import RiskDecision
from .realtime_guard import DataQuality

DENY = "DENY"
ALLOW = "ALLOW"


@dataclass(frozen=True)
class TradeGuardDecision:
    action: str
    allowed: bool
    reason: str
    quantity: float = 0.0


def evaluate_trade_guard(
    *,
    signal: EngineSignal,
    data_quality: DataQuality,
    portfolio_risk: PortfolioRiskDecision,
    risk: RiskDecision,
    position_open: bool = False,
) -> TradeGuardDecision:
    """Apply all hard pre-execution safety checks to an existing signal.

    The function is intentionally fail-closed: WAIT, bad data, a portfolio
    halt, an unavailable risk decision, an open position, or an invalid
    quantity can never produce ALLOW.
    """
    if not isinstance(signal, EngineSignal):
        raise ValueError("signal must be an EngineSignal")
    if not isinstance(data_quality, DataQuality):
        raise ValueError("data_quality must be a DataQuality")
    if not isinstance(portfolio_risk, PortfolioRiskDecision):
        raise ValueError("portfolio_risk must be a PortfolioRiskDecision")
    if not isinstance(risk, RiskDecision):
        raise ValueError("risk must be a RiskDecision")
    if not isinstance(position_open, bool):
        raise ValueError("position_open must be bool")

    if signal.action == WAIT:
        return TradeGuardDecision(DENY, False, "strategy is WAIT")
    if signal.action not in {LONG, SHORT}:
        return TradeGuardDecision(DENY, False, "unknown strategy action")
    if not data_quality.ok:
        return TradeGuardDecision(DENY, False, f"data quality rejected: {data_quality.reason}")
    if portfolio_risk.action == HALT or not portfolio_risk.allowed:
        return TradeGuardDecision(DENY, False, f"portfolio risk rejected: {portfolio_risk.reason}")
    if position_open:
        return TradeGuardDecision(DENY, False, "position already open")
    if not risk.allowed:
        return TradeGuardDecision(DENY, False, f"trade risk rejected: {risk.reason}")
    if not isfinite(risk.quantity) or risk.quantity <= 0:
        return TradeGuardDecision(DENY, False, "risk decision quantity must be finite and > 0")

    return TradeGuardDecision(ALLOW, True, "all hard trade guards passed", risk.quantity)
