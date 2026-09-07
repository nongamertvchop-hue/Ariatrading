"""Evidence aggregation for leakage-safe historical research.

This module is deliberately diagnostic. It combines independently produced
walk-forward, ML, regime, feature-stability, and execution-robustness results
without selecting parameters, thresholds, scenarios, or strategies.
"""

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any

from .ml_stability import MLStabilityReport
from .ml_walk_forward import MLWalkForwardResult
from .regime import RegimeStats
from .research_runner import ControlledResearchResult
from .robustness import RobustnessReport


@dataclass(frozen=True)
class ValidationEvidence:
    """Immutable, JSON-serializable summary of independent research evidence."""

    evidence_sha256: str
    timeframe: str
    dataset_sha256: str
    config_sha256: str
    walk_forward: dict[str, Any]
    ml: dict[str, Any]
    regime: tuple[dict[str, Any], ...]
    stability: dict[str, Any] | None
    robustness: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize evidence with deterministic key ordering."""
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _walk_forward_payload(controlled: ControlledResearchResult) -> dict[str, Any]:
    result = controlled.walk_forward
    return {
        "fold_count": result.fold_count,
        "metrics": asdict(result.metrics),
        "folds": [
            {
                "fold_index": fold.fold_index,
                "history_start": fold.history_start,
                "test_start": fold.test_start,
                "test_end": fold.test_end,
                "trade_count": len(fold.backtest.trades),
            }
            for fold in result.folds
        ],
    }


def _ml_payload(result: MLWalkForwardResult) -> dict[str, Any]:
    return {
        "fold_count": result.fold_count,
        "trained_fold_count": result.trained_fold_count,
        "threshold": result.threshold,
        "horizon_bars": result.horizon_bars,
        "baseline_metrics": asdict(result.baseline_metrics),
        "filtered_metrics": asdict(result.filtered_metrics),
        "baseline_trade_count": len(result.baseline_trades),
        "filtered_trade_count": len(result.filtered_trades),
        "folds": [
            {
                "fold_index": fold.fold_index,
                "train_samples": fold.train_samples,
                "train_positive": fold.train_positive,
                "test_labeled_samples": fold.test_labeled_samples,
                "model_trained": fold.model_trained,
            }
            for fold in result.folds
        ],
    }


def _stability_payload(report: MLStabilityReport) -> dict[str, Any]:
    return {
        "sample_count": report.sample_count,
        "feature_count": report.feature_count,
        "baseline_accuracy": report.baseline_accuracy,
        "importance": [asdict(item) for item in report.importance],
    }


def _robustness_payload(report: RobustnessReport) -> dict[str, Any]:
    return {
        "case_count": report.case_count,
        "scenario_names": report.scenario_names,
        "net_r_range": report.net_r_range,
        "expectancy_r_range": report.expectancy_r_range,
        "cases": [
            {"name": case.name, "metrics": asdict(case.metrics)}
            for case in report.cases
        ],
    }


def build_validation_evidence(
    controlled: ControlledResearchResult,
    ml_result: MLWalkForwardResult,
    *,
    regime_stats: tuple[RegimeStats, ...] | list[RegimeStats] = (),
    stability: MLStabilityReport | None = None,
    robustness: RobustnessReport | None = None,
) -> ValidationEvidence:
    """Aggregate independent diagnostics without changing research decisions."""
    if controlled.walk_forward.timeframe != ml_result.timeframe:
        raise ValueError("controlled and ML results must use the same timeframe")
    if robustness is not None and robustness.timeframe != ml_result.timeframe:
        raise ValueError("robustness report must use the same timeframe")
    for item in regime_stats:
        if not item.regime or not item.regime.strip():
            raise ValueError("regime name must be non-empty")

    control = controlled.control
    payload = {
        "timeframe": ml_result.timeframe,
        "dataset_sha256": control.dataset.sha256,
        "config_sha256": control.config_sha256,
        "walk_forward": _walk_forward_payload(controlled),
        "ml": _ml_payload(ml_result),
        "regime": [asdict(item) for item in regime_stats],
        "stability": None if stability is None else _stability_payload(stability),
        "robustness": None if robustness is None else _robustness_payload(robustness),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    evidence_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return ValidationEvidence(
        evidence_sha256=evidence_sha256,
        timeframe=ml_result.timeframe,
        dataset_sha256=control.dataset.sha256,
        config_sha256=control.config_sha256,
        walk_forward=payload["walk_forward"],
        ml=payload["ml"],
        regime=tuple(payload["regime"]),
        stability=payload["stability"],
        robustness=payload["robustness"],
    )


__all__ = ["ValidationEvidence", "build_validation_evidence"]
