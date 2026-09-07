from strategy.broker_contract import ContractValidation
from strategy.engine import EngineSignal, LONG
from strategy.execution_recovery import ExecutionRecoveryDecision, ExecutionRecoveryReport
from strategy.portfolio_risk import PortfolioRiskDecision
from strategy.position_reconciliation import ReconciliationDecision
from strategy.realtime_guard import DataQuality
from strategy.risk_engine import RiskDecision
from strategy.system_gate import ALLOW, DENY, evaluate_system_readiness


def _inputs():
    return dict(
        signal=EngineSignal(LONG, "confirmed support rejection", "15m", protection="SAFE"),
        data_quality=DataQuality(True, "ok"),
        portfolio_risk=PortfolioRiskDecision("ALLOW", True, "ok", 0.0, 0.0, 0),
        risk=RiskDecision(True, "risk checks passed", quantity=1.0, risk_amount=10.0, risk_fraction=0.001),
        reconciliation=ReconciliationDecision("ALLOW", True, "local and broker are both flat", 0),
        execution_recovery=ExecutionRecoveryReport(
            ExecutionRecoveryDecision.ALLOW,
            order_count=0,
            audit_event_count=0,
            checked_order_count=0,
            issues=(),
        ),
    )


def test_system_gate_allows_only_when_all_hard_checks_pass():
    decision = evaluate_system_readiness(**_inputs())
    assert decision.action == ALLOW
    assert decision.allowed is True
    assert decision.quantity == 1.0
    assert decision.checks == (
        "strategy=SAFE",
        "data=OK",
        "portfolio-risk=OK",
        "trade-risk=OK",
        "position-state=FLAT",
        "execution-recovery=OK",
    )


def test_system_gate_accepts_valid_broker_contract():
    values = _inputs()
    values["broker_contract"] = ContractValidation(True, "broker symbol contract passed")
    decision = evaluate_system_readiness(**values)
    assert decision.action == ALLOW
    assert "broker-contract=OK" in decision.checks


def test_system_gate_blocks_invalid_broker_contract():
    values = _inputs()
    values["broker_contract"] = ContractValidation(False, "quantity is below broker minimum")
    decision = evaluate_system_readiness(**values)
    assert decision.action == DENY
    assert "broker contract rejected" in decision.reason


def test_system_gate_fails_closed_when_recovery_is_missing():
    values = _inputs()
    values["execution_recovery"] = None
    decision = evaluate_system_readiness(**values)
    assert decision.action == DENY
    assert "recovery report is required" in decision.reason


def test_system_gate_blocks_unsafe_strategy_even_when_other_checks_pass():
    values = _inputs()
    values["signal"] = EngineSignal(LONG, "blocked", "15m", protection="BLOCKED")
    decision = evaluate_system_readiness(**values)
    assert decision.action == DENY
    assert "protection is not SAFE" in decision.reason


def test_system_gate_blocks_new_entry_when_broker_has_existing_position():
    values = _inputs()
    values["reconciliation"] = ReconciliationDecision(
        "ALLOW", True, "local and broker position reconciled", 1
    )
    decision = evaluate_system_readiness(**values)
    assert decision.action == DENY
    assert "existing broker position" in decision.reason


def test_system_gate_can_require_ml_evidence_without_changing_direction():
    values = _inputs()
    decision = evaluate_system_readiness(**values, require_ml_evidence=True)
    assert decision.action == DENY
    assert "required ML evidence is missing" in decision.reason


def test_system_gate_rejects_risk_quantity_that_is_not_executable():
    values = _inputs()
    values["risk"] = RiskDecision(True, "ok", quantity=0.0, risk_amount=0.0, risk_fraction=0.0)
    decision = evaluate_system_readiness(**values)
    assert decision.action == DENY
    assert "quantity must be finite and > 0" in decision.reason
