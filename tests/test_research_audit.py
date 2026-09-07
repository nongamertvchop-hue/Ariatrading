from types import SimpleNamespace

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


def _fold(*, fold_index=1, test_start=10, test_end=20, train_samples=10,
          train_positive=5, test_labeled_samples=4, model_trained=True,
          train_last_signal_index=6, train_last_label_end_index=9,
          test_first_signal_index=12, test_last_signal_index=18):
    return SimpleNamespace(
        fold_index=fold_index,
        test_start=test_start,
        test_end=test_end,
        train_samples=train_samples,
        train_positive=train_positive,
        test_labeled_samples=test_labeled_samples,
        model_trained=model_trained,
        train_last_signal_index=train_last_signal_index,
        train_last_label_end_index=train_last_label_end_index,
        test_first_signal_index=test_first_signal_index,
        test_last_signal_index=test_last_signal_index,
        baseline=SimpleNamespace(signals=(SimpleNamespace(action="LONG"),) * 4),
    )


def _ml(*, folds=None, history_bars=10, test_bars=10, step_bars=10):
    if folds is None:
        folds = (_fold(),)
    return SimpleNamespace(
        timeframe="1h",
        history_bars=history_bars,
        test_bars=test_bars,
        step_bars=step_bars,
        horizon_bars=3,
        fold_count=len(folds),
        trained_fold_count=sum(fold.model_trained for fold in folds),
        folds=tuple(folds),
    )


def test_audit_passes_consistent_evidence():
    report = audit_validation_evidence(_evidence(), _ml())
    assert report.passed
    assert report.status == "PASS"


def test_audit_flags_missing_optional_evidence_without_failing_consistency():
    report = audit_validation_evidence(
        _evidence(stability=False, robustness=False), _ml()
    )
    assert report.passed
    assert any("stability evidence is absent" in item for item in report.findings)
    assert any("robustness evidence is absent" in item for item in report.findings)


def test_audit_rejects_invalid_ml_threshold():
    ml = _ml()
    evidence = _evidence()
    evidence.ml["threshold"] = 1.0
    report = audit_validation_evidence(evidence, ml)
    assert not report.passed
    assert any("threshold must be between 0 and 1" in item for item in report.findings)


def test_audit_rejects_overlapping_oos_windows():
    folds = (_fold(), _fold(fold_index=2, test_start=19, test_end=29))
    evidence = _evidence()
    evidence.ml["fold_count"] = 2
    evidence.ml["trained_fold_count"] = 2
    report = audit_validation_evidence(evidence, _ml(folds=folds))
    assert not report.passed
    assert any("OOS test windows overlap" in item for item in report.findings)


def test_audit_rejects_incorrect_fold_spacing():
    folds = (_fold(), _fold(fold_index=2, test_start=25, test_end=35))
    evidence = _evidence()
    evidence.ml["fold_count"] = 2
    evidence.ml["trained_fold_count"] = 2
    report = audit_validation_evidence(evidence, _ml(folds=folds))
    assert not report.passed
    assert any("fold spacing disagrees" in item for item in report.findings)


def test_audit_rejects_trained_fold_without_two_classes():
    fold = _fold(train_samples=10, train_positive=0, model_trained=True)
    report = audit_validation_evidence(_evidence(), _ml(folds=(fold,)))
    assert not report.passed
    assert any("two-class training data" in item for item in report.findings)


def test_audit_rejects_training_label_crossing_oos_boundary():
    fold = _fold(train_last_signal_index=8, train_last_label_end_index=10)
    report = audit_validation_evidence(_evidence(), _ml(folds=(fold,)))
    assert not report.passed
    assert any("training label ending at or after OOS start" in item for item in report.findings)


def test_audit_rejects_inconsistent_training_horizon():
    fold = _fold(train_last_signal_index=6, train_last_label_end_index=8)
    report = audit_validation_evidence(_evidence(), _ml(folds=(fold,)))
    assert not report.passed
    assert any("inconsistent training label horizon" in item for item in report.findings)


def test_audit_rejects_test_signal_outside_oos_window():
    fold = _fold(test_first_signal_index=9, test_last_signal_index=18)
    report = audit_validation_evidence(_evidence(), _ml(folds=(fold,)))
    assert not report.passed
    assert any("first test signal outside OOS window" in item for item in report.findings)
