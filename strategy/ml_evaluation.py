"""Evaluation helpers for comparing baseline and ML-filtered research results.

This module only summarizes already-separated out-of-sample results. It never
selects a threshold, retrains a model, or mutates trades.
"""

from dataclasses import dataclass

from .validation import ResearchMetrics


@dataclass(frozen=True)
class MLComparison:
    baseline: ResearchMetrics
    filtered: ResearchMetrics
    baseline_trade_count: int
    filtered_trade_count: int
    trades_removed: int
    trade_reduction_ratio: float
    net_r_delta: float
    expectancy_r_delta: float
    win_rate_delta: float

    @property
    def filtered_trade_fraction(self) -> float:
        if self.baseline_trade_count == 0:
            return 0.0
        return self.filtered_trade_count / self.baseline_trade_count


def compare_ml_results(
    baseline_metrics: ResearchMetrics,
    filtered_metrics: ResearchMetrics,
    *,
    baseline_trade_count: int,
    filtered_trade_count: int,
) -> MLComparison:
    """Compare OOS baseline and filtered research metrics without optimization."""
    if baseline_trade_count < 0 or filtered_trade_count < 0:
        raise ValueError("trade counts must be >= 0")
    if filtered_trade_count > baseline_trade_count:
        raise ValueError("filtered_trade_count cannot exceed baseline_trade_count")

    removed = baseline_trade_count - filtered_trade_count
    reduction = removed / baseline_trade_count if baseline_trade_count else 0.0
    return MLComparison(
        baseline=baseline_metrics,
        filtered=filtered_metrics,
        baseline_trade_count=baseline_trade_count,
        filtered_trade_count=filtered_trade_count,
        trades_removed=removed,
        trade_reduction_ratio=reduction,
        net_r_delta=filtered_metrics.net_r - baseline_metrics.net_r,
        expectancy_r_delta=filtered_metrics.expectancy_r - baseline_metrics.expectancy_r,
        win_rate_delta=filtered_metrics.win_rate - baseline_metrics.win_rate,
    )


__all__ = ["MLComparison", "compare_ml_results"]
