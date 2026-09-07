"""Consistency and leakage-audit diagnostics for historical research.

The audit is intentionally non-optimizing: it reports structural problems in
research evidence and never changes strategy parameters, thresholds, or
execution behavior.
"""

from dataclasses import dataclass
from math import isfinite

from .ml_walk_forward import MLWalkForwardResult
from .research_validation import ValidationEvidence


@dataclass(frozen=True)
class ResearchAuditReport:
    """Immutable audit result for a research evidence record."""

    status: str
    findings: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


def audit_validation_evidence(
    evidence: ValidationEvidence,
    ml_result: MLWalkForwardResult,
) -> ResearchAuditReport:
    """Check evidence consistency and basic anti-leakage invariants.

    Fold boundaries are checked against the walk-forward configuration so a
    malformed or manually altered result cannot silently present overlapping
    or reversed OOS windows as valid evidence.
    """
    findings: list[str] = []
    errors: list[str] = []

    if evidence.timeframe != ml_result.timeframe:
        errors.append("evidence and ML result use different timeframes")

    ml = evidence.ml
    if ml["fold_count"] != ml_result.fold_count:
        errors.append("ML fold count disagrees with evidence")
    if ml["trained_fold_count"] != ml_result.trained_fold_count:
        errors.append("ML trained-fold count disagrees with evidence")

    folds = tuple(ml_result.folds)
    previous_test_start = None
    previous_test_end = None
    for expected_index, fold in enumerate(folds, start=1):
        if fold.fold_index != expected_index:
            errors.append(
                f"fold ordering/index mismatch at expected fold {expected_index}"
            )
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
        baseline_signal_count = len(fold.baseline.signals)
        if fold.test_labeled_samples > baseline_signal_count:
            errors.append(
                f"fold {fold.fold_index} has more labeled test samples than signals"
            )
        if fold.model_trained and not (
            fold.train_samples >= 2 and 0 < fold.train_positive < fold.train_samples
        ):
            errors.append(
                f"fold {fold.fold_index} is marked trained without two-class training data"
            )
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
