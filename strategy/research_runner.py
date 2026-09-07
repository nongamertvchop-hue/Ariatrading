"""Controlled, reproducible historical research runner."""

from dataclasses import dataclass

from .backtest import ENTRY_TIMING_SIGNAL_REFERENCE
from .execution import ExecutionModel
from .research_control import ResearchRun, build_research_run
from .research_control import ResearchConfig
from .walk_forward import WalkForwardResult, walk_forward_backtest


@dataclass(frozen=True)
class ControlledResearchResult:
    """Research output bound to the exact configuration and dataset fingerprints."""

    control: ResearchRun
    walk_forward: WalkForwardResult


def run_controlled_research(
    candles: list[dict],
    config: ResearchConfig,
    *,
    mtf_candles_by_timeframe: dict[str, list[dict]] | None = None,
    execution_model: ExecutionModel | None = None,
) -> ControlledResearchResult:
    """Run walk-forward validation while binding reproducibility metadata."""
    if config.step_bars < config.test_bars:
        raise ValueError("step_bars must be >= test_bars")

    control = build_research_run(config, candles)
    result = walk_forward_backtest(
        candles,
        config.timeframe,
        history_bars=config.history_bars,
        test_bars=config.test_bars,
        step_bars=config.step_bars,
        reward_risk=config.reward_risk,
        max_hold_bars=config.max_hold_bars,
        mtf_candles_by_timeframe=mtf_candles_by_timeframe,
        execution_model=execution_model,
        entry_timing=config.entry_timing or ENTRY_TIMING_SIGNAL_REFERENCE,
    )
    return ControlledResearchResult(control=control, walk_forward=result)


__all__ = ["ControlledResearchResult", "run_controlled_research"]
