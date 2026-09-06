"""Rolling out-of-sample validation for Ariatrading.

This module does not optimize strategy parameters. It repeatedly evaluates a
future test window while allowing the strategy to see only candles that existed
before each decision. The test window is hard-bounded so exits cannot consume
later observations.
"""

from dataclasses import dataclass

from .backtest import BacktestResult, run_backtest
from .execution import ExecutionModel
from .risk import TradeResult
from .validation import ResearchMetrics, evaluate_trades


@dataclass(frozen=True)
class WalkForwardFold:
    """One rolling-origin out-of-sample evaluation window."""

    fold_index: int
    history_start: int
    test_start: int
    test_end: int
    backtest: BacktestResult
    metrics: ResearchMetrics


@dataclass(frozen=True)
class WalkForwardResult:
    """Combined result from all completed walk-forward folds."""

    timeframe: str
    history_bars: int
    test_bars: int
    step_bars: int
    folds: tuple[WalkForwardFold, ...]
    trades: tuple[TradeResult, ...]
    metrics: ResearchMetrics

    @property
    def fold_count(self) -> int:
        return len(self.folds)

    @property
    def total_test_bars(self) -> int:
        return sum(fold.backtest.candles_tested for fold in self.folds)


def walk_forward_backtest(
    candles: list[dict],
    timeframe: str,
    *,
    history_bars: int,
    test_bars: int,
    step_bars: int | None = None,
    reward_risk: float = 2.0,
    max_hold_bars: int = 20,
    mtf_candles_by_timeframe: dict[str, list[dict]] | None = None,
    execution_model: ExecutionModel | None = None,
) -> WalkForwardResult:
    """Run expanding-history, non-overlapping out-of-sample backtests.

    The first test window starts after ``history_bars``. Subsequent folds begin
    after the previous fold when ``step_bars`` is at least ``test_bars``. The
    default is ``step_bars == test_bars`` so test observations are never counted
    in more than one fold. Strategy decisions can use all earlier candles, while
    exit simulation is capped at each fold's ``test_end`` boundary.
    """
    if history_bars < 1:
        raise ValueError("history_bars must be >= 1")
    if test_bars < 1:
        raise ValueError("test_bars must be >= 1")
    if step_bars is None:
        step_bars = test_bars
    if step_bars < test_bars:
        raise ValueError("step_bars must be >= test_bars for non-overlapping folds")
    if len(candles) <= history_bars:
        raise ValueError("candles must contain data after the history window")

    folds: list[WalkForwardFold] = []
    all_trades: list[TradeResult] = []
    test_start = history_bars
    fold_index = 1

    while test_start < len(candles):
        test_end = min(test_start + test_bars, len(candles))
        result = run_backtest(
            candles,
            timeframe,
            reward_risk=reward_risk,
            max_hold_bars=max_hold_bars,
            mtf_candles_by_timeframe=mtf_candles_by_timeframe,
            execution_model=execution_model,
            start_index=test_start,
            end_index=test_end,
        )
        metrics = evaluate_trades(result.trades)
        fold = WalkForwardFold(
            fold_index=fold_index,
            history_start=0,
            test_start=test_start,
            test_end=test_end,
            backtest=result,
            metrics=metrics,
        )
        folds.append(fold)
        all_trades.extend(result.trades)
        fold_index += 1
        test_start += step_bars

    return WalkForwardResult(
        timeframe=timeframe,
        history_bars=history_bars,
        test_bars=test_bars,
        step_bars=step_bars,
        folds=tuple(folds),
        trades=tuple(all_trades),
        metrics=evaluate_trades(all_trades),
    )


__all__ = ["WalkForwardFold", "WalkForwardResult", "walk_forward_backtest"]
