"""Research-only diagnostics for ML filter behavior across OOS folds.

The deterministic two-setup strategy remains the source of direction. This
module only measures how the already-trained ML filter changes OOS behavior
from fold to fold; it never selects thresholds or changes signals.
"""

from dataclasses import dataclass
from math import isfinite

from .ml_walk_forward import MLWalkForwardResult


@dataclass(frozen=True)
class MLBehaviorFold:
    """Observed ML filter impact for one out-of-sample fold."""

    fold_index: int
    baseline_trades: int
    filtered_trades: int
    trade_reduction_ratio: float
    net_r_delta: float
    expectancy_r_delta: float
    win_rate_delta: float
    drawdown_r_delta: float


@dataclass(frozen=True)
class MLBehaviorReport:
    """Aggregate fold-to-fold ML filter behavior diagnostics."""

    fold_count: int
    trained_fold_count: int
    folds: tuple[MLBehaviorFold, ...]
    mean_net_r_delta: float
    mean_expectancy_r_delta: float
    mean_win_rate_delta: float
    mean_drawdown_r_delta: float


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _validate_finite(value: float, name: str) -> None:
    if not isfinite(float(value)):
        raise ValueError(f"{name} must be finite")


def analyze_ml_behavior(result: MLWalkForwardResult) -> MLBehaviorReport:
    """Measure ML filter impact across already-computed OOS folds.

    This is descriptive only. In particular, it does not choose a threshold,
    drop adverse folds, or declare profitability from historical results.
    """
    diagnostics: list[MLBehaviorFold] = []
    for fold in result.folds:
        baseline_metrics = fold.baseline
        filtered_metrics = fold.filtered
        baseline_count = len(baseline_metrics.trades)
        filtered_count = len(filtered_metrics.trades)
        if filtered_count > baseline_count:
            raise ValueError("filtered trade count cannot exceed baseline trade count")

        reduction = (baseline_count - filtered_count) / baseline_count if baseline_count else 0.0
        values = {
            "trade_reduction_ratio": reduction,
            "net_r_delta": filtered_metrics.net_r - baseline_metrics.net_r,
            "expectancy_r_delta": filtered_metrics.expectancy_r - baseline_metrics.expectancy_r,
            "win_rate_delta": filtered_metrics.win_rate - baseline_metrics.win_rate,
            "drawdown_r_delta": filtered_metrics.max_drawdown_r - baseline_metrics.max_drawdown_r,
        }
        for name, value in values.items():
            _validate_finite(value, name)
        diagnostics.append(
            MLBehaviorFold(
                fold_index=fold.fold_index,
                baseline_trades=baseline_count,
                filtered_trades=filtered_count,
                trade_reduction_ratio=reduction,
                net_r_delta=values["net_r_delta"],
                expectancy_r_delta=values["expectancy_r_delta"],
                win_rate_delta=values["win_rate_delta"],
                drawdown_r_delta=values["drawdown_r_delta"],
            )
        )

    return MLBehaviorReport(
        fold_count=len(diagnostics),
        trained_fold_count=result.trained_fold_count,
        folds=tuple(diagnostics),
        mean_net_r_delta=_mean([item.net_r_delta for item in diagnostics]),
        mean_expectancy_r_delta=_mean([item.expectancy_r_delta for item in diagnostics]),
        mean_win_rate_delta=_mean([item.win_rate_delta for item in diagnostics]),
        mean_drawdown_r_delta=_mean([item.drawdown_r_delta for item in diagnostics]),
    )


__all__ = ["MLBehaviorFold", "MLBehaviorReport", "analyze_ml_behavior"]
