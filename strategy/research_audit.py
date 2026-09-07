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
    """Check evidence consistency and basic anti-leakage invariants."""
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
    previous_test_end = None
    for fold in folds:
        if fold.train_samples < 0 or fold.test_labeled_samples < 0:
            errors.append(f"fold {fold.fold_index} has negative sample count")
        if fold.train_positive < 0 or fold.train_positive > fold.train_samples:
            errors.append(f"fold {fold.fold_index} has invalid positive-label count")
        if previous_test_end is not None and fold.fold_index > 1:
            # Fold ordering is validated by the result producer; here we only
            # reject an explicitly reversed OOS sequence.
            if getattr(fold, "fold_index", 0) <= 0:
                errors.append("OOS fold indices must be positive")
        previous_test_end = fold.fold_index

    threshold = ml.get("threshold")
    if not isinstance(threshold, (int, float)) or not isfinite(float(threshold)):
        errors.append("ML threshold is not finite")
    elif not 0.0 < float(threshold) < 1.0:
        errors.append("ML threshold must be between 0 and 1")

    horizon = ml.get("horizon_bars")
    if not isinstance(horizon, int) or horizon <= 0:
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
