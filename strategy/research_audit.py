"""Consistency and leakage-audit diagnostics for historical research."""

from dataclasses import dataclass
from math import isfinite

from .ml_walk_forward import MLWalkForwardResult
from .research_validation import ValidationEvidence


@dataclass(frozen=True)
class ResearchAuditReport:
    status: str
    findings: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


def _valid_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def audit_validation_evidence(evidence: ValidationEvidence, ml_result: MLWalkForwardResult) -> ResearchAuditReport:
    """Check evidence consistency and temporal/feature anti-leakage invariants."""
    findings: list[str] = []
    errors: list[str] = []

    if evidence.timeframe != ml_result.timeframe:
        errors.append("evidence and ML result use different timeframes")
    ml = evidence.ml
    if ml["fold_count"] != ml_result.fold_count:
        errors.append("ML fold count disagrees with evidence")
    if ml["trained_fold_count"] != ml_result.trained_fold_count:
        errors.append("ML trained-fold count disagrees with evidence")

    evidence_folds = {item["fold_index"]: item for item in ml.get("folds", []) if isinstance(item, dict) and "fold_index" in item}
    folds = tuple(ml_result.folds)
    previous_test_start = None
    previous_test_end = None
    for expected_index, fold in enumerate(folds, start=1):
        if fold.fold_index != expected_index:
            errors.append(f"fold ordering/index mismatch at expected fold {expected_index}")
        if fold.test_start < ml_result.history_bars:
            errors.append(f"fold {fold.fold_index} starts before history window")
        if fold.test_end <= fold.test_start:
            errors.append(f"fold {fold.fold_index} has invalid test boundaries")
        if previous_test_start is not None and fold.test_start <= previous_test_start:
            errors.append("OOS fold starts are not strictly increasing")
        if previous_test_end is not None:
            if fold.test_start < previous_test_end:
                errors.append("OOS test windows overlap")
            if fold.test_start - previous_test_start != ml_result.step_bars:
                errors.append("OOS fold spacing disagrees with step_bars")

        if fold.train_samples < 0 or fold.test_labeled_samples < 0:
            errors.append(f"fold {fold.fold_index} has negative sample count")
        if fold.train_positive < 0 or fold.train_positive > fold.train_samples:
            errors.append(f"fold {fold.fold_index} has invalid positive-label count")
        directional_test_count = sum(1 for signal in fold.baseline.signals if signal.action in {"LONG", "SHORT"})
        if fold.test_labeled_samples > directional_test_count:
            errors.append(f"fold {fold.fold_index} has invalid labeled test-sample provenance")
        if fold.model_trained and not (fold.train_samples >= 2 and 0 < fold.train_positive < fold.train_samples):
            errors.append(f"fold {fold.fold_index} is marked trained without two-class training data")

        if fold.train_samples == 0:
            if fold.train_last_signal_index is not None or fold.train_last_label_end_index is not None:
                errors.append(f"fold {fold.fold_index} has training provenance without samples")
        elif fold.train_last_signal_index is None or fold.train_last_label_end_index is None:
            errors.append(f"fold {fold.fold_index} is missing training temporal provenance")
        else:
            if not 0 <= fold.train_last_signal_index < fold.test_start:
                errors.append(f"fold {fold.fold_index} has training signal outside history")
            if fold.train_last_label_end_index != fold.train_last_signal_index + ml_result.horizon_bars:
                errors.append(f"fold {fold.fold_index} has inconsistent training label horizon")
            if fold.train_last_label_end_index >= fold.test_start:
                errors.append(f"fold {fold.fold_index} has training label ending at or after OOS start")

        if fold.test_first_signal_index is None or fold.test_last_signal_index is None:
            if directional_test_count:
                errors.append(f"fold {fold.fold_index} is missing test signal provenance")
        else:
            if not fold.test_start <= fold.test_first_signal_index < fold.test_end:
                errors.append(f"fold {fold.fold_index} has first test signal outside OOS window")
            if not fold.test_start <= fold.test_last_signal_index < fold.test_end:
                errors.append(f"fold {fold.fold_index} has last test signal outside OOS window")
            if fold.test_first_signal_index > fold.test_last_signal_index:
                errors.append(f"fold {fold.fold_index} has reversed test signal provenance")

        evidence_fold = evidence_folds.get(fold.fold_index)
        if evidence_fold is None:
            errors.append(f"fold {fold.fold_index} is missing from ML evidence")
        else:
            for field in ("train_last_signal_index", "train_last_label_end_index", "test_first_signal_index", "test_last_signal_index"):
                if evidence_fold.get(field) != getattr(fold, field):
                    errors.append(f"fold {fold.fold_index} {field} disagrees with evidence")
            for field in ("train_feature_sha256", "test_feature_sha256"):
                value = getattr(fold, field, None)
                if not _valid_sha256(value):
                    errors.append(f"fold {fold.fold_index} has invalid {field}")
                elif evidence_fold.get(field) != value:
                    errors.append(f"fold {fold.fold_index} {field} disagrees with evidence")

        previous_test_start = fold.test_start
        previous_test_end = fold.test_end

    threshold = ml.get("threshold")
    if not isinstance(threshold, (int, float)) or not isfinite(float(threshold)):
        errors.append("ML threshold is not finite")
    elif not 0.0 < float(threshold) < 1.0:
        errors.append("ML threshold must be between 0 and 1")
    horizon = ml.get("horizon_bars")
    if not isinstance(horizon, int) or isinstance(horizon, bool) or horizon <= 0:
        errors.append("ML label horizon must be a positive integer")

    if evidence.stability is None:
        findings.append("feature stability evidence is absent")
    elif evidence.stability["sample_count"] <= 0:
        errors.append("feature stability has no samples")
    else:
        findings.append("feature stability evidence is present")
    if evidence.robustness is None:
        findings.append("execution robustness evidence is absent")
    elif evidence.robustness["case_count"] < 2:
        errors.append("execution robustness needs at least two scenarios")
    else:
        findings.append("multi-scenario execution robustness is present")
    if not evidence.regime:
        findings.append("regime stratification evidence is absent")
    else:
        findings.append(f"regime stratification contains {len(evidence.regime)} buckets")

    if errors:
        findings.extend(f"ERROR: {message}" for message in errors)
        return ResearchAuditReport(status="FAIL", findings=tuple(findings))
    findings.insert(0, "core evidence consistency checks passed")
    return ResearchAuditReport(status="PASS", findings=tuple(findings))


__all__ = ["ResearchAuditReport", "audit_validation_evidence"]
