"""Ariatrading price-action research package.

The package keeps the two core setups stable while exposing consistent
interfaces across strategy, forecast, backtest, execution-cost simulation,
replay, realtime monitoring, paper simulation, journaling, walk-forward
validation, and research metrics.
"""

from .engine import EngineSignal, LONG, SHORT, WAIT, evaluate_long, evaluate_short
from .execution import ExecutionModel
from .forecast import ForecastResult, HorizonForecast, ScenarioForecast, forecast
from .journal import JournalEvent, PaperTradeJournal
from .market_snapshot import MarketSnapshot
from .paper import CLOSED, OPEN, PaperAccount, PaperPosition, PaperTradingEngine
from .paper_session import PaperSessionResult, PaperSessionRunner
from .pipeline import ResearchReport, run_research
from .realtime_guard import DataQuality, RealtimeGuard, expected_closed_bar_open
from .realtime_supervisor import ALLOW, SupervisorDecision, supervise
from .replay import ReplayPoint, ReplayResult, replay_forecasts
from .walk_forward import WalkForwardFold, WalkForwardResult, walk_forward_backtest

__all__ = [
    "EngineSignal", "LONG", "SHORT", "WAIT", "evaluate_long", "evaluate_short",
    "ExecutionModel", "ForecastResult", "HorizonForecast", "ScenarioForecast", "forecast",
    "JournalEvent", "PaperTradeJournal",
    "MarketSnapshot", "ReplayPoint", "ReplayResult", "replay_forecasts",
    "DataQuality", "RealtimeGuard", "expected_closed_bar_open",
    "ALLOW", "SupervisorDecision", "supervise", "ResearchReport", "run_research",
    "CLOSED", "OPEN", "PaperAccount", "PaperPosition", "PaperTradingEngine",
    "PaperSessionResult", "PaperSessionRunner",
    "WalkForwardFold", "WalkForwardResult", "walk_forward_backtest",
]
