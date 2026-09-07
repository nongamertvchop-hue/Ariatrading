"""Ariatrading price-action research package.

The package keeps the two core setups stable while exposing consistent
interfaces across strategy, forecast, backtest, execution-cost simulation,
replay, realtime monitoring, paper simulation, journaling, walk-forward
validation, robustness analysis, reproducible research control, ML
meta-filter research, experiment registry, regime diagnostics, aggregated
research evidence, research-gate completeness checks, and audit diagnostics.
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
from .experiment_registry import ExperimentRecord, build_experiment_record
from .forecast import ForecastResult, HorizonForecast, ScenarioForecast, forecast
from .journal import JournalEvent, PaperTradeJournal
from .market_snapshot import MarketSnapshot
from .ml_evaluation import MLComparison, compare_ml_results
from .ml_features import FEATURE_NAMES, MLSample, build_signal_sample, extract_signal_features
from .ml_meta import MLResearchMetrics, MetaFilterModel, MetaFilterResult, chronological_train_test
from .ml_stability import FeatureImportance, MLStabilityReport, permutation_feature_importance
from .ml_walk_forward import MLWalkForwardFold, MLWalkForwardResult, ml_walk_forward_backtest
from .order_state import OrderRecord, OrderState, OrderStateMachine, OrderTransition
from .paper import CLOSED, OPEN, PaperAccount, PaperPosition, PaperTradingEngine
from .paper_session import PaperSessionResult, PaperSessionRunner
from .pipeline import ResearchReport, run_research
from .portfolio_risk import ALLOW as PORTFOLIO_ALLOW, HALT, PortfolioRiskController, PortfolioRiskDecision, PortfolioRiskLimits, PortfolioRiskState
from .position_reconciliation import (
    FLAT,
    LocalPositionState,
    PositionSnapshot,
    ReconciliationDecision,
    new_entry_allowed,
    reconcile_position,
)
from .realtime_guard import DataQuality, RealtimeGuard, expected_closed_bar_open
from .realtime_replay import RealtimeReplayResult, replay_realtime_monitor
from .realtime_supervisor import ALLOW, SupervisorDecision, supervise
from .replay import ReplayPoint, ReplayResult, replay_forecasts
from .research_audit import ResearchAuditReport, audit_validation_evidence
from .research_control import (
    DatasetFingerprint,
    ResearchConfig,
    ResearchRun,
    build_research_run,
    config_fingerprint,
    fingerprint_candles,
)
from .research_gate import INCOMPLETE, READY, ResearchGateDecision, evaluate_research_gate
from .research_runner import ControlledResearchResult, run_controlled_research
from .research_validation import ValidationEvidence, build_validation_evidence
from .regime import REGIMES, RegimeStats, classify_regime, stratify_samples
from .risk_engine import RiskDecision, RiskLimits, evaluate_risk, position_size
from .trade_guard import TradeGuardDecision, evaluate_trade_guard
from .two_setups import TwoSetupResult, evaluate_two_setups
from .walk_forward import WalkForwardFold, WalkForwardResult, walk_forward_backtest

__all__ = [
    "EngineSignal", "LONG", "SHORT", "WAIT", "evaluate_long", "evaluate_short",
    "TwoSetupResult", "evaluate_two_setups",
    "RiskLimits", "RiskDecision", "position_size", "evaluate_risk",
    "PortfolioRiskLimits", "PortfolioRiskState", "PortfolioRiskDecision",
    "PortfolioRiskController", "PORTFOLIO_ALLOW", "HALT",
    "PositionSnapshot", "LocalPositionState", "ReconciliationDecision",
    "reconcile_position", "new_entry_allowed", "FLAT",
    "TradeGuardDecision", "evaluate_trade_guard",
    "OrderState", "OrderRecord", "OrderTransition", "OrderStateMachine",
    "ExecutionModel", "entry_price", "exit_price",
    "ExperimentRecord", "build_experiment_record",
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
    "ValidationEvidence", "build_validation_evidence",
    "INCOMPLETE", "READY", "ResearchGateDecision", "evaluate_research_gate",
    "ResearchAuditReport", "audit_validation_evidence",
    "FEATURE_NAMES", "MLSample", "build_signal_sample", "extract_signal_features",
    "MLResearchMetrics", "MetaFilterModel", "chronological_train_test",
    "WalkForwardFold", "WalkForwardResult", "walk_forward_backtest",
    "MLWalkForwardFold", "MLWalkForwardResult", "ml_walk_forward_backtest",
    "MLComparison", "compare_ml_results",
    "FeatureImportance", "MLStabilityReport", "permutation_feature_importance",
    "REGIMES", "RegimeStats", "classify_regime", "stratify_samples",
]
