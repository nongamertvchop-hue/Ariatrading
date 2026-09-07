from types import SimpleNamespace

import pytest

from strategy.ml_stability import FeatureImportance, MLStabilityReport
from strategy.regime import RegimeStats
from strategy.research_gate import INCOMPLETE, READY, evaluate_research_gate
from strategy.robustness import RobustnessReport


def _ml_result(trained=2, folds=2):
    return SimpleNamespace(
        fold_count=folds,
        trained_fold_count=trained,
    )


def _stability():
    return MLStabilityReport(
        sample_count=10,
        feature_count=2,
        baseline_accuracy=0.8,
        importance=(FeatureImportance(0, 0.2, 0.01, 3),),
    )


def test_gate_ready_when_all_required_evidence_is_present():
    decision = evaluate_research_gate(
        _ml_result(),
        regime_stats=(RegimeStats("BULLISH", 5, 3),),
        stability_report=_stability(),
        robustness_report=RobustnessReport(timeframe="1h", cases=(object(), object())),
    )

    assert decision.status == READY
    assert decision.ready


def test_gate_incomplete_when_any_required_evidence_is_missing():
    decision = evaluate_research_gate(
        _ml_result(trained=1),
        regime_stats=(RegimeStats("RANGE", 5, 2),),
        stability_report=_stability(),
        robustness_report=RobustnessReport(timeframe="1h", cases=(object(),)),
    )

    assert decision.status == INCOMPLETE
    assert not decision.ready
    assert any("1/2" in reason for reason in decision.reasons)


def test_gate_requires_at_least_one_fold():
    with pytest.raises(ValueError, match="at least one fold"):
        evaluate_research_gate(_ml_result(folds=0, trained=0))


def test_gate_validates_stability_dimensions():
    invalid = MLStabilityReport(
        sample_count=0,
        feature_count=2,
        baseline_accuracy=0.8,
        importance=(),
    )
    with pytest.raises(ValueError, match="samples and features"):
        evaluate_research_gate(_ml_result(), stability_report=invalid)
