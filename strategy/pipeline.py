"""High-level integration facade for the Ariatrading research system."""

from dataclasses import dataclass

from .backtest import (
    ENTRY_TIMING_SIGNAL_REFERENCE,
    BacktestResult,
    run_all_timeframes,
    run_backtest,
)
from .execution import ExecutionModel
from .validation import ChronologicalSplit, ResearchMetrics, bootstrap_expectancy_ci, chronological_split, evaluate_trades


@dataclass(frozen=True)
class ResearchReport:
    """One coherent research output for a completed backtest."""
    backtest: BacktestResult
    metrics: ResearchMetrics
    split: ChronologicalSplit
    expectancy_ci: tuple[float, float]


def run_research(
    candles: list[dict],
    timeframe: str,
    *,
    warmup: int | None = None,
    reward_risk: float = 2.0,
    max_hold_bars: int = 20,
    mtf_candles_by_timeframe: dict[str, list[dict]] | None = None,
    execution_model: ExecutionModel | None = None,
    train_ratio: float = 0.60,
    validation_ratio: float = 0.20,
    bootstrap_iterations: int = 2000,
    bootstrap_confidence: float = 0.95,
    bootstrap_seed: int = 42,
    entry_timing: str = ENTRY_TIMING_SIGNAL_REFERENCE,
) -> ResearchReport:
    """Run strategy, risk, optional execution costs, and validation together."""
    result = run_backtest(
        candles,
        timeframe,
        warmup=warmup,
        reward_risk=reward_risk,
        max_hold_bars=max_hold_bars,
        mtf_candles_by_timeframe=mtf_candles_by_timeframe,
        execution_model=execution_model,
        entry_timing=entry_timing,
    )
    metrics = evaluate_trades(result.trades)
    split = chronological_split(result.trades, train_ratio, validation_ratio)
    ci = bootstrap_expectancy_ci(
        result.trades,
        iterations=bootstrap_iterations,
        confidence=bootstrap_confidence,
        seed=bootstrap_seed,
    )
    return ResearchReport(result, metrics, split, ci)


__all__ = ["ResearchReport", "run_research", "run_backtest", "run_all_timeframes"]
