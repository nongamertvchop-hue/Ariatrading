"""Robustness analysis for historical Ariatrading research.

This module evaluates the same strategy and data under explicitly supplied
execution-cost scenarios. It never chooses or optimizes a scenario; every case
is returned so researchers can inspect sensitivity to friction assumptions.
"""

from dataclasses import dataclass

from .backtest import ENTRY_TIMING_SIGNAL_REFERENCE
from .execution import ExecutionModel
from .validation import ResearchMetrics
from .walk_forward import WalkForwardResult, walk_forward_backtest


@dataclass(frozen=True)
class RobustnessScenario:
    """Named execution assumptions used for one independent research run."""

    name: str
    execution_model: ExecutionModel

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("scenario name must be non-empty")


@dataclass(frozen=True)
class RobustnessCase:
    """One scenario result plus the exact assumptions used to produce it."""

    name: str
    execution_model: ExecutionModel
    walk_forward: WalkForwardResult

    @property
    def metrics(self) -> ResearchMetrics:
        return self.walk_forward.metrics


@dataclass(frozen=True)
class RobustnessReport:
    """Sensitivity report containing every supplied scenario result."""

    timeframe: str
    cases: tuple[RobustnessCase, ...]

    @property
    def scenario_names(self) -> tuple[str, ...]:
        return tuple(case.name for case in self.cases)

    @property
    def case_count(self) -> int:
        return len(self.cases)

    @property
    def net_r_range(self) -> tuple[float, float]:
        if not self.cases:
            return (0.0, 0.0)
        values = [case.metrics.net_r for case in self.cases]
        return (min(values), max(values))

    @property
    def expectancy_r_range(self) -> tuple[float, float]:
        if not self.cases:
            return (0.0, 0.0)
        values = [case.metrics.expectancy_r for case in self.cases]
        return (min(values), max(values))


def run_robustness_analysis(
    candles: list[dict],
    timeframe: str,
    *,
    scenarios: list[RobustnessScenario] | tuple[RobustnessScenario, ...],
    history_bars: int,
    test_bars: int,
    step_bars: int | None = None,
    reward_risk: float = 2.0,
    max_hold_bars: int = 20,
    mtf_candles_by_timeframe: dict[str, list[dict]] | None = None,
    entry_timing: str = ENTRY_TIMING_SIGNAL_REFERENCE,
) -> RobustnessReport:
    """Run identical walk-forward research under all supplied cost scenarios.

    Scenarios are deliberately evaluated independently. The function does not
    rank, select, or tune scenarios, which avoids turning execution assumptions
    into an optimization parameter.
    """
    cases: list[RobustnessCase] = []
    seen_names: set[str] = set()
    for scenario in scenarios:
        if scenario.name in seen_names:
            raise ValueError(f"duplicate scenario name: {scenario.name}")
        seen_names.add(scenario.name)
        result = walk_forward_backtest(
            candles,
            timeframe,
            history_bars=history_bars,
            test_bars=test_bars,
            step_bars=step_bars,
            reward_risk=reward_risk,
            max_hold_bars=max_hold_bars,
            mtf_candles_by_timeframe=mtf_candles_by_timeframe,
            execution_model=scenario.execution_model,
            entry_timing=entry_timing,
        )
        cases.append(
            RobustnessCase(
                name=scenario.name,
                execution_model=scenario.execution_model,
                walk_forward=result,
            )
        )

    return RobustnessReport(timeframe=timeframe, cases=tuple(cases))


__all__ = ["RobustnessScenario", "RobustnessCase", "RobustnessReport", "run_robustness_analysis"]
