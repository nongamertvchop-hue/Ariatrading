"""Ariatrading price-action research package.

The package keeps the two core setups stable while exposing one high-level
research facade for consistent orchestration across strategy, forecast,
backtest, execution-cost simulation, replay, and validation layers.
"""

from .engine import EngineSignal, LONG, SHORT, WAIT, evaluate_long, evaluate_short
from .execution import ExecutionModel
from .forecast import ForecastResult, HorizonForecast, ScenarioForecast, forecast
from .pipeline import ResearchReport, run_research
from .replay import ReplayPoint, ReplayResult, replay_forecasts

__all__ = [
    "EngineSignal",
    "LONG",
    "SHORT",
    "WAIT",
    "evaluate_long",
    "evaluate_short",
    "ExecutionModel",
    "ForecastResult",
    "HorizonForecast",
    "ScenarioForecast",
    "forecast",
    "ReplayPoint",
    "ReplayResult",
    "replay_forecasts",
    "ResearchReport",
    "run_research",
]
