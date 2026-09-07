"""Completeness gate for historical research evidence.

The gate is intentionally not a profitability gate. It only answers whether a
research run contains the minimum independent evidence needed for a disciplined
review. It never promotes a strategy to live execution or changes parameters.
"""

from dataclasses import dataclass

from .ml_stability import MLStabilityReport
from .ml_walk_forward import MLWalkForwardResult
from .regime import RegimeStats
from .robustness import RobustnessReport

READY = "READY"
INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class ResearchGateDecision:
    """Immutable result of the evidence-completeness gate."""

    status: str
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.status not in {READY, INCOMPLETE}:
            raise ValueError(f"unsupported research gate status: {self.status}")
        if not self.reasons:
            raise ValueError("gate decision must contain at least one reason")

    @property
    def ready(self) -> bool:
        return self.status == READY


def evaluate_research_gate(
    ml_result: MLWalkForwardResult,
    *,
    regime_stats: tuple[RegimeStats, ...] | list[RegimeStats] | None = None,
    stability_report: MLStabilityReport | None = None,
    robustness_report: RobustnessReport | None = None,
) -> ResearchGateDecision:
    """Check evidence completeness without evaluating profitability.

    A run is READY only when every OOS fold was trained and regime,
stability,
and multi-scenario execution evidence are present. This deliberately makes
    incomplete experiments visible instead of silently treating missing
    diagnostics as positive evidence.
    """
    reasons: list[str] = []

    if ml_result.fold_count < 1:
        raise ValueError("ML result must contain at least one fold")
    if ml_result.trained_fold_count == ml_result.fold_count:
        reasons.append("all OOS folds have trained ML models")
    else:
        reasons.append(
            f"only {ml_result.trained_fold_count}/{ml_result.fold_count} OOS folds have trained ML models"
        )

    if regime_stats:
        reasons.append(f"regime evidence contains {len(regime_stats)} buckets")
    else:
        reasons.append("regime evidence is missing")

    if stability_report is not None:
        if stability_report.sample_count < 1 or stability_report.feature_count < 1:
            raise ValueError("stability report must contain samples and features")
        reasons.append("feature-stability evidence is present")
    else:
        reasons.append("feature-stability evidence is missing")

    if robustness_report is not None and robustness_report.case_count >= 2:
        reasons.append(f"execution robustness contains {robustness_report.case_count} scenarios")
    elif robustness_report is None:
        reasons.append("execution robustness evidence is missing")
    else:
        reasons.append("execution robustness has fewer than two scenarios")

    ready = (
        ml_result.trained_fold_count == ml_result.fold_count
        and bool(regime_stats)
        and stability_report is not None
        and stability_report.sample_count > 0
        and stability_report.feature_count > 0
        and robustness_report is not None
        and robustness_report.case_count >= 2
    )
    return ResearchGateDecision(status=READY if ready else INCOMPLETE, reasons=tuple(reasons))


__all__ = ["INCOMPLETE", "READY", "ResearchGateDecision", "evaluate_research_gate"]
