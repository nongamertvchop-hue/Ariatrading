from types import SimpleNamespace

from strategy.ml_evidence_gate import INCOMPLETE, READY, MLEvidencePolicy, evaluate_ml_evidence_gate
from strategy.ml_drift import FeatureDrift, MLDriftReport


def _ml_result():
    return SimpleNamespace(fold_count=2, trained_fold_count=2)


def _stability():
    return SimpleNamespace(sample_count=20, feature_count=3)


def _robustness():
    return SimpleNamespace(case_count=3)


def _behavior():
    return SimpleNamespace(fold_count=2)


def _drift():
    return MLDriftReport(
        train_sample_count=20,
        test_sample_count=10,
        feature_count=1,
        features=(FeatureDrift(0, 0.0, 0.1, 1.0, 1.0, 0.1, 0.02),),
    )


def _dl(model_type):
    return SimpleNamespace(model_type=model_type, train_samples=10, test_samples=5, valid=True)


def test_gate_requires_explicit_evidence_and_is_ready_when_complete():
    decision = evaluate_ml_evidence_gate(
        _ml_result(), regime_stats=(object(),), stability_report=_stability(),
        robustness_report=_robustness(), behavior_report=_behavior(), drift_report=_drift(),
    )
    assert decision.status == READY
    assert decision.ready


def test_gate_fails_closed_when_required_drift_is_missing():
    decision = evaluate_ml_evidence_gate(
        _ml_result(), regime_stats=(object(),), stability_report=_stability(),
        robustness_report=_robustness(), behavior_report=_behavior(), drift_report=None,
    )
    assert decision.status == INCOMPLETE
    assert not decision.ready
    assert any("drift evidence is missing" in reason for reason in decision.reasons)


def test_gate_can_require_both_lstm_and_transformer():
    policy = MLEvidencePolicy(
        require_regime=False, require_stability=False, require_robustness=False,
        require_behavior=False, require_drift=False, require_deep_learning=True,
        require_both_deep_learning_models=True,
    )
    incomplete = evaluate_ml_evidence_gate(_ml_result(), policy=policy, deep_learning_metrics=(_dl("lstm"),))
    assert incomplete.status == INCOMPLETE

    ready = evaluate_ml_evidence_gate(
        _ml_result(), policy=policy,
        deep_learning_metrics=(_dl("lstm"), _dl("transformer")),
    )
    assert ready.status == READY
