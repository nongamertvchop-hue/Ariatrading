"""Ariatrading price-action research package.

The package keeps the two core setups stable while exposing consistent
interfaces across strategy, forecast, backtest, execution-cost simulation,
replay, realtime monitoring, paper simulation, and validation.
"""

from .engine import EngineSignal, LONG, SHORT, WAIT, evaluate_long, evaluate_short
from .execution import ExecutionModel
from .forecast import ForecastResult, HorizonForecast, ScenarioForecast, forecast
from .market_snapshot import MarketSnapshot
from .paper import CLOSED, OPEN, PaperAccount, PaperPosition, PaperTradingEngine
from .pipeline import ResearchReport, run_research
from .realtime_guard import DataQuality, RealtimeGuard, expected_closed_bar_open
from .realtime_supervisor import ALLOW, SupervisorDecision, supervise
from .replay import ReplayPoint, ReplayResult, replay_forecasts

__all__ = [
    "EngineSignal", "LONG", "SHORT", "WAIT", "evaluate_long", "evaluate_short",
    "ExecutionModel", "ForecastResult", "HorizonForecast", "ScenarioForecast", "forecast",
    "MarketSnapshot", "ReplayPoint", "ReplayResult", "replay_forecasts",
    "DataQuality", "RealtimeGuard", "expected_closed_bar_open",
    "ALLOW", "SupervisorDecision", "supervise", "ResearchReport", "run_research",
    "CLOSED", "OPEN", "PaperAccount", "PaperPosition", "PaperTradingEngine",
]
