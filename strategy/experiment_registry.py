"""Immutable experiment records for reproducible ML research.

The registry is metadata-only: it records exactly what was evaluated and never
selects an OOS threshold, retrains a model, or changes strategy decisions.
Records are deterministic except for the human-audit timestamp.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Sequence

from .ml_evaluation import MLComparison, compare_ml_results
from .ml_stability import MLStabilityReport
from .ml_walk_forward import MLWalkForwardResult
from .regime import RegimeStats
from .research_runner import ControlledResearchResult
from .robustness import RobustnessReport


@dataclass(frozen=True)
class ExperimentRecord:
    """Immutable, serializable description of one completed ML experiment."""

    experiment_sha256: str
    created_at: str
    control: dict[str, Any]
    model_name: str
    model_params: dict[str, Any]
    ml: dict[str, Any]
    validation: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe copy of the record."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize the record with stable key ordering."""
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _stable_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _stable_payload(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_stable_payload(item) for item in value]
    if isinstance(value, float):
        return format(value, ".17g")
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    raise TypeError(f"unsupported experiment value type: {type(value).__name__}")


def _comparison_payload(comparison: MLComparison) -> dict[str, Any]:
    return {
        "baseline_trade_count": comparison.baseline_trade_count,
        "filtered_trade_count": comparison.filtered_trade_count,
        "trades_removed": comparison.trades_removed,
        "trade_reduction_ratio": comparison.trade_reduction_ratio,
        "net_r_delta": comparison.net_r_delta,
        "expectancy_r_delta": comparison.expectancy_r_delta,
        "win_rate_delta": comparison.win_rate_delta,
        "drawdown_r_delta": comparison.drawdown_r_delta,
        "baseline_metrics": asdict(comparison.baseline),
        "filtered_metrics": asdict(comparison.filtered),
    }


def _ml_payload(result: MLWalkForwardResult, comparison: MLComparison) -> dict[str, Any]:
    return {
        "timeframe": result.timeframe,
        "history_bars": result.history_bars,
        "test_bars": result.test_bars,
        "step_bars": result.step_bars,
        "threshold": result.threshold,
        "horizon_bars": result.horizon_bars,
        "fold_count": result.fold_count,
        "trained_fold_count": result.trained_fold_count,
        "folds": [
            {
                "fold_index": fold.fold_index,
                "test_start": fold.test_start,
                "test_end": fold.test_end,
                "train_samples": fold.train_samples,
                "train_positive": fold.train_positive,
                "test_labeled_samples": fold.test_labeled_samples,
                "model_trained": fold.model_trained,
                "baseline_trade_count": len(fold.baseline.trades),
                "filtered_trade_count": len(fold.filtered.trades),
            }
            for fold in result.folds
        ],
        "comparison": _comparison_payload(comparison),
    }


def _validation_payload(
    regime_stats: Sequence[RegimeStats] | None,
    stability_report: MLStabilityReport | None,
    robustness_report: RobustnessReport | None,
) -> dict[str, Any]:
    """Serialize independent validation diagnostics without selecting winners."""
    payload: dict[str, Any] = {}
    if regime_stats is not None:
        payload["regime"] = {
            "stats": [asdict(item) | {"positive_rate": item.positive_rate} for item in regime_stats],
        }
    if stability_report is not None:
        payload["stability"] = asdict(stability_report)
    if robustness_report is not None:
        payload["robustness"] = {
            "timeframe": robustness_report.timeframe,
            "cases": [
                {
                    "name": case.name,
                    "execution_model": asdict(case.execution_model),
                    "metrics": asdict(case.metrics),
                }
                for case in robustness_report.cases
            ],
        }
    return payload


def build_experiment_record(
    controlled: ControlledResearchResult,
    ml_result: MLWalkForwardResult,
    *,
    model_name: str = "HistGradientBoostingClassifier",
    model_params: dict[str, Any] | None = None,
    regime_stats: Sequence[RegimeStats] | None = None,
    stability_report: MLStabilityReport | None = None,
    robustness_report: RobustnessReport | None = None,
    created_at: datetime | None = None,
) -> ExperimentRecord:
    """Build a deterministic experiment record from completed OOS results.

    Validation diagnostics are optional and are recorded verbatim. They are
    never ranked, optimized, or used to alter the strategy or ML threshold.
    """
    if not model_name or not model_name.strip():
        raise ValueError("model_name must be non-empty")
    if created_at is None:
        created_at = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        raise ValueError("created_at must be timezone-aware")
    if controlled.walk_forward.timeframe != ml_result.timeframe:
        raise ValueError("controlled and ML results must use the same timeframe")
    if controlled.walk_forward.history_bars != ml_result.history_bars:
        raise ValueError("controlled and ML results must use the same history_bars")
    if controlled.walk_forward.test_bars != ml_result.test_bars:
        raise ValueError("controlled and ML results must use the same test_bars")
    if controlled.walk_forward.step_bars != ml_result.step_bars:
        raise ValueError("controlled and ML results must use the same step_bars")

    comparison = compare_ml_results(
        ml_result.baseline_metrics,
        ml_result.filtered_metrics,
        baseline_trade_count=len(ml_result.baseline_trades),
        filtered_trade_count=len(ml_result.filtered_trades),
    )
    control_payload = controlled.control
    control = {
        "config": asdict(control_payload.config),
        "config_sha256": control_payload.config_sha256,
        "dataset": asdict(control_payload.dataset),
    }
    ml = _ml_payload(ml_result, comparison)
    validation = _validation_payload(regime_stats, stability_report, robustness_report)
    params = dict(model_params or {})
    fingerprint_payload = {
        "control": control,
        "model_name": model_name,
        "model_params": params,
        "ml": ml,
        "validation": validation,
    }
    canonical = json.dumps(_stable_payload(fingerprint_payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    experiment_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return ExperimentRecord(
        experiment_sha256=experiment_sha256,
        created_at=created_at.astimezone(timezone.utc).isoformat(),
        control=control,
        model_name=model_name,
        model_params=params,
        ml=ml,
        validation=validation,
    )


__all__ = ["ExperimentRecord", "build_experiment_record"]
