"""Fail-closed system readiness gate before any live execution boundary.

This module is an orchestration safety layer. It does not generate signals,
select ML models, or place broker orders. It verifies that independently
computed strategy, data, portfolio-risk, trade-risk, reconciliation,
execution-recovery, and optional ML-evidence decisions agree before an
execution adapter is allowed to proceed.

The two deterministic LONG/SHORT setups remain the only source of direction.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .engine import EngineSignal, LONG, SHORT, WAIT
from .execution_recovery import ExecutionRecoveryDecision, ExecutionRecoveryReport
from .ml_evidence_gate import MLEvidenceDecision
from .portfolio_risk import PortfolioRiskDecision
from .position_reconciliation import ReconciliationDecision
from .realtime_guard import DataQuality
from .risk_engine import RiskDecision

DENY = "DENY"
ALLOW = "ALLOW"


@dataclass(frozen=True)
class SystemGateDecision:
    """Final fail-closed readiness decision for a new position."""

    action: str
    allowed: bool
    reason: str
    quantity: float = 0.0
    checks: tuple[str, ...] = ()


def evaluate_system_readiness(
    *,
    signal: EngineSignal,
    data_quality: DataQuality,
    portfolio_risk: PortfolioRiskDecision,
    risk: RiskDecision,
    reconciliation: ReconciliationDecision,
    execution_recovery: ExecutionRecoveryReport | None,
    ml_evidence: MLEvidenceDecision | None = None,
    require_ml_evidence: bool = False,
) -> SystemGateDecision:
    """Combine all hard pre-execution safety contracts into one decision.

    The function is deliberately fail-closed. A missing recovery report, an
    unsafe strategy state, bad data, portfolio/risk rejection, an existing
    broker position, a position-state mismatch, or missing required ML
    evidence produces DENY. ML evidence can be required explicitly, but it
    never changes LONG/SHORT direction by itself.
    """
    if not isinstance(signal, EngineSignal):
        raise ValueError("signal must be an EngineSignal")
    if not isinstance(data_quality, DataQuality):
        raise ValueError("data_quality must be a DataQuality")
    if not isinstance(portfolio_risk, PortfolioRiskDecision):
        raise ValueError("portfolio_risk must be a PortfolioRiskDecision")
    if not isinstance(risk, RiskDecision):
        raise ValueError("risk must be a RiskDecision")
    if not isinstance(reconciliation, ReconciliationDecision):
        raise ValueError("reconciliation must be a ReconciliationDecision")
    if execution_recovery is not None and not isinstance(execution_recovery, ExecutionRecoveryReport):
        raise ValueError("execution_recovery must be an ExecutionRecoveryReport or None")
    if ml_evidence is not None and not isinstance(ml_evidence, MLEvidenceDecision):
        raise ValueError("ml_evidence must be an MLEvidenceDecision or None")
    if not isinstance(require_ml_evidence, bool):
        raise ValueError("require_ml_evidence must be bool")

    checks: list[str] = []

    if signal.action == WAIT:
        return SystemGateDecision(DENY, False, "strategy is WAIT", checks=tuple(checks))
    if signal.action not in {LONG, SHORT}:
        return SystemGateDecision(DENY, False, "unknown strategy action", checks=tuple(checks))
    if signal.protection != "SAFE":
        return SystemGateDecision(DENY, False, "strategy protection is not SAFE", checks=tuple(checks))
    checks.append("strategy=SAFE")

    if not data_quality.ok:
        return SystemGateDecision(DENY, False, f"data quality rejected: {data_quality.reason}", checks=tuple(checks))
    checks.append("data=OK")

    if not portfolio_risk.allowed:
        return SystemGateDecision(DENY, False, f"portfolio risk rejected: {portfolio_risk.reason}", checks=tuple(checks))
    checks.append("portfolio-risk=OK")

    if not risk.allowed:
        return SystemGateDecision(DENY, False, f"trade risk rejected: {risk.reason}", checks=tuple(checks))
    if not isfinite(risk.quantity) or risk.quantity <= 0:
        return SystemGateDecision(DENY, False, "risk quantity must be finite and > 0", checks=tuple(checks))
    checks.append("trade-risk=OK")

    if not reconciliation.safe:
        return SystemGateDecision(
            DENY,
            False,
            f"position reconciliation rejected: {reconciliation.reason}",
            checks=tuple(checks),
        )
    if reconciliation.broker_count != 0:
        return SystemGateDecision(
            DENY,
            False,
            "existing broker position prevents new entry",
            checks=tuple(checks),
        )
    checks.append("position-state=FLAT")

    if execution_recovery is None:
        return SystemGateDecision(
            DENY,
            False,
            "execution recovery report is required before execution",
            checks=tuple(checks),
        )
    if execution_recovery.decision != ExecutionRecoveryDecision.ALLOW:
        detail = "; ".join(execution_recovery.issues) or "no recovery details supplied"
        return SystemGateDecision(
            DENY,
            False,
            "execution recovery is not safe: " + detail,
            checks=tuple(checks),
        )
    checks.append("execution-recovery=OK")

    if require_ml_evidence:
        if ml_evidence is None:
            return SystemGateDecision(
                DENY,
                False,
                "required ML evidence is missing",
                checks=tuple(checks),
            )
        if not ml_evidence.ready:
            detail = "; ".join(ml_evidence.reasons) or "evidence gate is incomplete"
            return SystemGateDecision(
                DENY,
                False,
                "ML evidence gate rejected: " + detail,
                checks=tuple(checks),
            )
        checks.append("ml-evidence=READY")
    elif ml_evidence is not None and ml_evidence.ready:
        checks.append("ml-evidence=READY(optional)")

    return SystemGateDecision(
        ALLOW,
        True,
        "all system pre-execution gates passed",
        risk.quantity,
        tuple(checks),
    )


__all__ = ["ALLOW", "DENY", "SystemGateDecision", "evaluate_system_readiness"]
