"""Ariatrading price-action research package.

The package keeps the two core setups stable while exposing consistent
interfaces across strategy, forecast, backtest, execution-cost simulation,
replay, realtime monitoring, paper simulation, journaling, walk-forward
validation, robustness analysis, reproducible research control, and ML
meta-filter research.
"""

from .backtest import (
    ENTRY_TIMING_NEXT_BAR_OPEN,
    ENTRY_TIMING_SIGNAL_REFERENCE,
    BacktestResult,
    run_all_timeframes,
    run_backtest,
)
from .engine import EngineSignal, LONG, SHORT, WAIT, evaluate_long, evaluate_short
from .execution import ExecutionModel, entry_price, exit_price
from .forecast import ForecastResult, HorizonForecast, ScenarioForecast, forecast
from .journal import JournalEvent, PaperTradeJournal
from .market_snapshot import MarketSnapshot
from .ml_evaluation import MLComparison, compare_ml_results
from .ml_features import FEATURE_NAMES, MLSample, build_signal_sample, extract_signal_features
from .ml_meta import MLResearchMetrics, MetaFilterModel, MetaFilterResult, chronological_train_test
from .ml_walk_forward import MLWalkForwardFold, MLWalkForwardResult, ml_walk_forward_backtest
from .paper import CLOSED, OPEN, PaperAccount, PaperPosition, PaperTradingEngine
from .paper_session import PaperSessionResult, PaperSessionRunner
from .pipeline import ResearchReport, run_research
from .realtime_guard import DataQuality, RealtimeGuard, expected_closed_bar_open
from .realtime_replay import RealtimeReplayResult, replay_realtime_monitor
from .realtime_supervisor import ALLOW, SupervisorDecision, supervise
from .replay import ReplayPoint, ReplayResult, replay_forecasts
from .research_control import (
    DatasetFingerprint,
    ResearchConfig,
    ResearchRun,
    build_research_run,
    config_fingerprint,
    fingerprint_candles,
)
from .research_runner import ControlledResearchResult, run_controlled_research
from .robustness import RobustnessCase, RobustnessReport, RobustnessScenario, run_robustness_analysis
from .walk_forward import WalkForwardFold, WalkForwardResult, walk_forward_backtest

__all__ = [
    "EngineSignal", "LONG", "SHORT", "WAIT", "evaluate_long", "evaluate_short",
    "ExecutionModel", "entry_price", "exit_price",
    "ForecastResult", "HorizonForecast", "ScenarioForecast", "forecast",
    "JournalEvent", "PaperTradeJournal",
    "MarketSnapshot", "ReplayPoint", "ReplayResult", "replay_forecasts",
    "DataQuality", "RealtimeGuard", "expected_closed_bar_open",
    "RealtimeReplayResult", "replay_realtime_monitor",
    "ALLOW", "SupervisorDecision", "supervise", "ResearchReport", "run_research",
    "BacktestResult", "run_backtest", "run_all_timeframes",
    "ENTRY_TIMING_SIGNAL_REFERENCE", "ENTRY_TIMING_NEXT_BAR_OPEN",
    "CLOSED", "OPEN", "PaperAccount", "PaperPosition", "PaperTradingEngine",
    "PaperSessionResult", "PaperSessionRunner",
    "RobustnessScenario", "RobustnessCase", "RobustnessReport", "run_robustness_analysis",
    "DatasetFingerprint", "ResearchConfig", "ResearchRun", "build_research_run",
    "config_fingerprint", "fingerprint_candles",
    "ControlledResearchResult", "run_controlled_research",
    "FEATURE_NAMES", "MLSample", "build_signal_sample", "extract_signal_features",
    "MLResearchMetrics", "MetaFilterModel", "MetaFilterResult", "chronological_train_test",
    "WalkForwardFold", "WalkForwardResult", "walk_forward_backtest",
    "MLWalkForwardFold", "MLWalkForwardResult", "ml_walk_forward_backtest",
    "MLComparison", "compare_ml_results",
]
