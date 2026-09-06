"""Ariatrading price-action research package.

The package keeps the two core setups stable while exposing one high-level
research facade for consistent orchestration across strategy, backtest,
execution-cost simulation, and validation layers.
"""

from .engine import EngineSignal, LONG, SHORT, WAIT, evaluate_long, evaluate_short
from .execution import ExecutionModel
from .pipeline import ResearchReport, run_research

__all__ = [
    "EngineSignal",
    "LONG",
    "SHORT",
    "WAIT",
    "evaluate_long",
    "evaluate_short",
    "ExecutionModel",
    "ResearchReport",
    "run_research",
]
