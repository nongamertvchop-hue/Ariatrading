from types import SimpleNamespace

from strategy.ml_stability import FeatureImportance, MLStabilityReport
from strategy.research_audit import audit_validation_evidence
from strategy.research_validation import ValidationEvidence


def _evidence(stability=True, robustness=True):
    return ValidationEvidence(
        evidence_sha256="evidence",
        timeframe="1h",
        dataset_sha256="dataset",
        config_sha256="config",
        walk_forward={"fold_count": 1},
        ml={
            "fold_count": 1,
            "trained_fold_count": 1,
            "threshold": 0.55,
            "horizon_bars": 3,
        },
        regime=({"regime": "BULLISH", "samples": 5, "positive": 3},),
        stability=(
            {"sample_count": 10, "feature_count": 2, "baseline_accuracy": 0.8,
             "importance": [
                 {"feature_index": 0, "mean_accuracy_drop": 0.2,
                  "std_accuracy_drop": 0.01, "repeats": 3}
             ]}
            if stability else None
        ),
        robustness=(
            {"case_count": 2, "scenario_names": ("base", "stress"),
             "net_r_range": 1.0, "expectancy_r_range": 0.5, "cases": []}
            if robustness else None
        ),
    )


def _ml():
    fold = SimpleNamespace(
        fold_index=1,
        train_samples=10,
        train_positive=5,
        test_labeled_samples=4,
    )
    return SimpleNamespace(timeframe="1h", fold_count=1, trained_fold_count=1, folds=(fold,))


def test_audit_passes_consistent_evidence():
    report = audit_validation_evidence(_evidence(), _ml())
    assert report.passed
    assert report.status == "PASS"


def test_audit_flags_missing_optional_evidence_without_failing_consistency():
    report = audit_validation_evidence(_evidence(stability=False, robustness=False), _ml())
    assert report.passed
    assert any("stability evidence is absent" in item for item in report.findings)
    assert any("robustness evidence is absent" in item for item in report.findings)


def test_audit_rejects_invalid_ml_threshold():
    ml = _ml()
    ml.threshold = 0.5
    evidence = _evidence()
    evidence.ml["threshold"] = 1.0
    report = audit_validation_evidence(evidence, ml)
    assert not report.passed
    assert any("threshold must be between 0 and 1" in item for item in report.findings)
