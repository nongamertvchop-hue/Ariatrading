"""Reporting helpers for chronological walk-forward research.

This module is descriptive only. It never selects parameters, promotes a model,
or changes strategy decisions. Every reported score is derived from the supplied
out-of-sample fold results in chronological order.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Sequence

from .backtest import BacktestResult
from .validation import ResearchMetrics, evaluate_trades


@dataclass(frozen=True)
class WalkForwardFoldReport:
    fold_index: int
    test_start: int
    test_end: int
    candles_tested: int
    trades: int
    closed_trades: int
    wins: int
    losses: int
    win_rate: float
    net_r: float
    expectancy_r: float
    profit_factor: float
    max_drawdown_r: float

    @classmethod
    def from_result(cls, fold_index: int, test_start: int, test_end: int, result: BacktestResult) -> "WalkForwardFoldReport":
        metrics = result.research_metrics()
        return cls(
            fold_index=fold_index,
            test_start=test_start,
            test_end=test_end,
            candles_tested=result.candles_tested,
            trades=metrics.trade_count,
            closed_trades=metrics.closed_trades,
            wins=metrics.wins,
            losses=metrics.losses,
            win_rate=metrics.win_rate,
            net_r=metrics.net_r,
            expectancy_r=metrics.expectancy_r,
            profit_factor=metrics.profit_factor,
            max_drawdown_r=metrics.max_drawdown_r,
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class WalkForwardReport:
    timeframe: str
    history_bars: int
    test_bars: int
    step_bars: int
    folds: tuple[WalkForwardFoldReport, ...]
    aggregate: ResearchMetrics

    @property
    def fold_count(self) -> int:
        return len(self.folds)

    @property
    def positive_net_r_folds(self) -> int:
        return sum(fold.net_r > 0 for fold in self.folds)

    @property
    def profitable_fold_ratio(self) -> float:
        return self.positive_net_r_folds / self.fold_count if self.fold_count else 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "timeframe": self.timeframe,
            "history_bars": self.history_bars,
            "test_bars": self.test_bars,
            "step_bars": self.step_bars,
            "fold_count": self.fold_count,
            "positive_net_r_folds": self.positive_net_r_folds,
            "profitable_fold_ratio": self.profitable_fold_ratio,
            "aggregate": asdict(self.aggregate),
            "folds": [fold.to_dict() for fold in self.folds],
        }


def build_walk_forward_report(
    timeframe: str,
    history_bars: int,
    test_bars: int,
    step_bars: int,
    folds: Sequence[tuple[int, int, BacktestResult]],
) -> WalkForwardReport:
    """Build a descriptive report from already-computed chronological OOS folds."""
    if not timeframe:
        raise ValueError("timeframe must be non-empty")
    if history_bars < 1 or test_bars < 1 or step_bars < test_bars:
        raise ValueError("invalid walk-forward window configuration")

    reports: list[WalkForwardFoldReport] = []
    trades = []
    previous_test_start = None
    for fold_index, test_start, result in folds:
        if fold_index < 1:
            raise ValueError("fold_index must be >= 1")
        if test_start < 0:
            raise ValueError("test_start must be >= 0")
        test_end = test_start + result.candles_tested
        if previous_test_start is not None and test_start <= previous_test_start:
            raise ValueError("folds must be supplied in chronological order")
        previous_test_start = test_start
        reports.append(WalkForwardFoldReport.from_result(fold_index, test_start, test_end, result))
        trades.extend(result.trades)

    return WalkForwardReport(
        timeframe=timeframe,
        history_bars=history_bars,
        test_bars=test_bars,
        step_bars=step_bars,
        folds=tuple(reports),
        aggregate=evaluate_trades(trades),
    )


__all__ = ["WalkForwardFoldReport", "WalkForwardReport", "build_walk_forward_report"]
