import strategy


def test_public_api_exports_robustness_and_execution_audit():
    assert strategy.RobustnessScenario
    assert strategy.RobustnessCase
    assert strategy.RobustnessReport
    assert strategy.run_robustness_analysis
    assert strategy.AuditEvent
    assert strategy.AuditJournal
    assert strategy.AuditJournalError


def test_public_api_exports_ml_diagnostics():
    assert strategy.FeatureDrift
    assert strategy.MLDriftReport
    assert strategy.analyze_feature_drift
    assert strategy.MLBehaviorFold
    assert strategy.MLBehaviorReport
    assert strategy.analyze_ml_behavior


def test_public_api_exports_execution_recovery():
    assert strategy.ExecutionRecoveryDecision
    assert strategy.ExecutionRecoveryReport
    assert strategy.verify_execution_recovery


def test_public_api_exports_ml_evidence_and_deep_learning():
    assert strategy.MLEvidencePolicy
    assert strategy.MLEvidenceDecision
    assert strategy.evaluate_ml_evidence_gate
    assert strategy.DeepLearningMetrics
    assert strategy.ModelType
    assert strategy.build_causal_sequences
    assert strategy.train_deep_sequence_model


def test_public_api_exports_system_readiness_and_dl_walk_forward():
    assert strategy.SystemGateDecision
    assert strategy.evaluate_system_readiness
    assert strategy.DeepLearningWalkForwardFold
    assert strategy.DeepLearningWalkForwardResult
    assert strategy.deep_learning_walk_forward_backtest
