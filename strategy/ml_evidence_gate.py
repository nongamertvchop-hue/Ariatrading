"""Explicit readiness gate for ML research evidence.

This gate is about evidence completeness and integrity, not profitability. It
never chooses a model, threshold, regime, scenario, or trading direction.
Deep-learning models are treated as challenger/meta-filter research only.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .ml_behavior import MLBehaviorReport
from .ml_drift import MLDriftReport
from .ml_walk_forward import MLWalkForwardResult
from .ml_stability import MLStabilityReport
from .robustness import RobustnessReport

READY = "READY"
INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class MLEvidencePolicy:
    """Explicit evidence requirements; no policy silently selects a model."""

    require_regime: bool = True
    require_stability: bool = True
    require_robustness: bool = True
    require_behavior: bool = True
    require_drift: bool = True
    require_deep_learning: bool = False
    require_both_deep_learning_models: bool = True


@dataclass(frozen=True)
class MLEvidenceDecision:
    status: str
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.status not in {READY, INCOMPLETE}:
            raise ValueError("unsupported ML evidence status")
        if not self.reasons:
            raise ValueError("evidence decision must contain at least one reason")

    @property
    def ready(self) -> bool:
        return self.status == READY


def _check_drift(report: MLDriftReport) -> tuple[bool, str]:
    if report.train_sample_count < 1 or report.test_sample_count < 1 or report.feature_count < 1:
        return False, "feature drift report has invalid dimensions"
    if len(report.features) != report.feature_count:
        return False, "feature drift report feature count is inconsistent"
    for item in report.features:
        if item.feature_index < 0 or item.feature_index >= report.feature_count:
            return False, "feature drift report contains an invalid feature index"
        for value in (item.train_mean, item.test_mean, item.train_std, item.test_std, item.mean_shift_std, item.psi):
            if not isfinite(float(value)):
                return False, "feature drift report contains a non-finite diagnostic"
    return True, "feature-drift evidence is structurally valid"


def _check_deep_learning(metrics: tuple[object, ...], require_both: bool) -> tuple[bool, str]:
    if not metrics:
        return False, "deep-learning evidence is missing"
    names = {str(getattr(item, "model_type", "")) for item in metrics}
    if require_both and not {"lstm", "transformer"}.issubset(names):
        return False, "both LSTM and Transformer evidence are required"
    for item in metrics:
        if not bool(getattr(item, "valid", False)):
            return False, "deep-learning evidence contains invalid metrics"
        if getattr(item, "train_samples", 0) < 1 or getattr(item, "test_samples", 0) < 1:
            return False, "deep-learning evidence has an empty train/test split"
    return True, "deep-learning challenger evidence is structurally valid"


def evaluate_ml_evidence_gate(
    ml_result: MLWalkForwardResult,
    *,
    policy: MLEvidencePolicy | None = None,
    regime_stats: tuple[object, ...] | list[object] | None = None,
    stability_report: MLStabilityReport | None = None,
    robustness_report: RobustnessReport | None = None,
    behavior_report: MLBehaviorReport | None = None,
    drift_report: MLDriftReport | None = None,
    deep_learning_metrics: tuple[object, ...] | list[object] | None = None,
) -> MLEvidenceDecision:
    """Evaluate whether the requested independent ML evidence is complete."""
    selected = policy or MLEvidencePolicy()
    reasons: list[str] = []

    if ml_result.fold_count < 1:
        raise ValueError("ML result must contain at least one fold")
    if ml_result.trained_fold_count != ml_result.fold_count:
        reasons.append(
            f"INCOMPLETE: only {ml_result.trained_fold_count}/{ml_result.fold_count} OOS folds are trained"
        )
    else:
        reasons.append("all OOS folds have trained models")

    checks: list[tuple[bool, str]] = []
    if selected.require_regime:
        checks.append((bool(regime_stats), "regime evidence is present" if regime_stats else "regime evidence is missing"))
    if selected.require_stability:
        valid = stability_report is not None and stability_report.sample_count > 0 and stability_report.feature_count > 0
        checks.append((valid, "feature-stability evidence is present" if valid else "feature-stability evidence is missing or invalid"))
    if selected.require_robustness:
        valid = robustness_report is not None and robustness_report.case_count >= 2
        checks.append((valid, "multi-scenario execution robustness is present" if valid else "execution robustness is missing or has fewer than two scenarios"))
    if selected.require_behavior:
        valid = behavior_report is not None and behavior_report.fold_count == ml_result.fold_count
        checks.append((valid, "fold-level ML behavior evidence is present" if valid else "fold-level ML behavior evidence is missing or incomplete"))
    if selected.require_drift:
        if drift_report is None:
            checks.append((False, "feature-drift evidence is missing"))
        else:
            checks.append(_check_drift(drift_report))
    if selected.require_deep_learning:
        checks.append(_check_deep_learning(tuple(deep_learning_metrics or ()), selected.require_both_deep_learning_models))

    for valid, message in checks:
        reasons.append(message)

    ready = ml_result.trained_fold_count == ml_result.fold_count and all(valid for valid, _ in checks)
    return MLEvidenceDecision(status=READY if ready else INCOMPLETE, reasons=tuple(reasons))


__all__ = [
    "READY",
    "INCOMPLETE",
    "MLEvidencePolicy",
    "MLEvidenceDecision",
    "evaluate_ml_evidence_gate",
]
