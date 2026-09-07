"""Ariatrading price-action research package.

The package keeps the two core setups stable while exposing consistent
interfaces across strategy, forecast, backtest, execution-cost simulation,
replay, realtime monitoring, paper simulation, journaling, walk-forward
validation, robustness analysis, reproducible research control, ML
meta-filter research, experiment registry, regime diagnostics, ML feature
drift diagnostics, ML OOS behavior diagnostics, ML model health diagnostics,
deep-learning challenger models, deep-learning walk-forward research,
aggregated research evidence, research-gate completeness checks, execution
recovery, and the final system readiness gate.
"""

from .backtest import ENTRY_TIMING_NEXT_BAR_OPEN, ENTRY_TIMING_SIGNAL_REFERENCE, BacktestResult, run_all_timeframes, run_backtest
from .deep_learning import DeepLearningMetrics, ModelType, build_causal_sequences, train_deep_sequence_model
from .deep_learning_walk_forward import DeepLearningWalkForwardFold, DeepLearningWalkForwardResult, deep_learning_walk_forward_backtest
from .engine import EngineSignal, LONG, SHORT, WAIT, evaluate_long, evaluate_short
from .execution import ExecutionModel, entry_price, exit_price
from .execution_audit import AuditEvent, AuditJournal, AuditJournalError
from .execution_recovery import ExecutionRecoveryDecision, ExecutionRecoveryReport, verify_execution_recovery
from .experiment_registry import ExperimentRecord, build_experiment_record
from .forecast import ForecastResult, HorizonForecast, ScenarioForecast, forecast
from .journal import JournalEvent, PaperTradeJournal
from .market_snapshot import MarketSnapshot
from .ml_behavior import MLBehaviorFold, MLBehaviorReport, analyze_ml_behavior
from .ml_drift import FeatureDrift, MLDriftReport, analyze_feature_drift
from .ml_evaluation import MLComparison, compare_ml_results
from .ml_evidence_gate import MLEvidenceDecision, MLEvidencePolicy, evaluate_ml_evidence_gate
from .ml_features import FEATURE_NAMES, MLSample, build_signal_sample, extract_signal_features
from .ml_meta import MLResearchMetrics, MetaFilterModel, MetaFilterResult, chronological_train_test
from .ml_model_health import CalibrationBin, MLModelHealth, MLModelHealthReport, analyze_model_health
from .ml_stability import FeatureImportance, MLStabilityReport, permutation_feature_importance
from .ml_walk_forward import MLWalkForwardFold, MLWalkForwardResult, ml_walk_forward_backtest
from .order_persistence import OrderPersistenceError, load_order_state, save_order_state
from .order_state import OrderRecord, OrderState, OrderStateMachine, OrderTransition
from .paper import CLOSED, OPEN, PaperAccount, PaperPosition, PaperTradingEngine
from .paper_session import PaperSessionResult, PaperSessionRunner
from .pipeline import ResearchReport, run_research
from .portfolio_risk import ALLOW as PORTFOLIO_ALLOW, HALT, PortfolioRiskController, PortfolioRiskDecision, PortfolioRiskLimits, PortfolioRiskState
from .position_reconciliation import FLAT, LocalPositionState, PositionSnapshot, ReconciliationDecision, new_entry_allowed, reconcile_position
from .realtime_guard import DataQuality, RealtimeGuard, expected_closed_bar_open
from .realtime_replay import RealtimeReplayResult, replay_realtime_monitor
from .realtime_supervisor import ALLOW, SupervisorDecision, supervise
from .replay import ReplayPoint, ReplayResult, replay_forecasts
from .research_audit import ResearchAuditReport, audit_validation_evidence
from .research_control import DatasetFingerprint, ResearchConfig, ResearchRun, build_research_run, config_fingerprint, fingerprint_candles
from .research_gate import INCOMPLETE, READY, ResearchGateDecision, evaluate_research_gate
from .research_runner import ControlledResearchResult, run_controlled_research
from .research_validation import ValidationEvidence, build_validation_evidence
from .regime import REGIMES, RegimeStats, classify_regime, stratify_samples
from .risk_engine import RiskDecision, RiskLimits, evaluate_risk, position_size
from .robustness import RobustnessCase, RobustnessReport, RobustnessScenario, run_robustness_analysis
from .system_gate import SystemGateDecision, evaluate_system_readiness
from .trade_guard import TradeGuardDecision, evaluate_trade_guard
from .two_setups import TwoSetupResult, evaluate_two_setups
from .walk_forward import WalkForwardFold, WalkForwardResult, walk_forward_backtest

__all__ = [
    "EngineSignal", "LONG", "SHORT", "WAIT", "evaluate_long", "evaluate_short",
    "TwoSetupResult", "evaluate_two_setups",
    "RiskLimits", "RiskDecision", "position_size", "evaluate_risk",
    "PortfolioRiskLimits", "PortfolioRiskState", "PortfolioRiskDecision", "PortfolioRiskController", "PORTFOLIO_ALLOW", "HALT",
    "PositionSnapshot", "LocalPositionState", "ReconciliationDecision", "reconcile_position", "new_entry_allowed", "FLAT",
    "TradeGuardDecision", "evaluate_trade_guard",
    "SystemGateDecision", "evaluate_system_readiness",
    "OrderState", "OrderRecord", "OrderTransition", "OrderStateMachine", "OrderPersistenceError", "save_order_state", "load_order_state",
    "AuditEvent", "AuditJournal", "AuditJournalError", "ExecutionRecoveryDecision", "ExecutionRecoveryReport", "verify_execution_recovery",
    "ExecutionModel", "entry_price", "exit_price",
    "ExperimentRecord", "build_experiment_record",
    "ForecastResult", "HorizonForecast", "ScenarioForecast", "forecast",
    "JournalEvent", "PaperTradeJournal", "MarketSnapshot", "ReplayPoint", "ReplayResult", "replay_forecasts",
    "DataQuality", "RealtimeGuard", "expected_closed_bar_open", "RealtimeReplayResult", "replay_realtime_monitor",
    "ALLOW", "SupervisorDecision", "supervise", "ResearchReport", "run_research",
    "BacktestResult", "run_backtest", "run_all_timeframes", "ENTRY_TIMING_SIGNAL_REFERENCE", "ENTRY_TIMING_NEXT_BAR_OPEN",
    "CLOSED", "OPEN", "PaperAccount", "PaperPosition", "PaperTradingEngine", "PaperSessionResult", "PaperSessionRunner",
    "RobustnessScenario", "RobustnessCase", "RobustnessReport", "run_robustness_analysis",
    "DatasetFingerprint", "ResearchConfig", "ResearchRun", "build_research_run", "config_fingerprint", "fingerprint_candles",
    "ControlledResearchResult", "run_controlled_research", "ValidationEvidence",
    "build_validation_evidence", "INCOMPLETE", "READY", "ResearchGateDecision", "evaluate_research_gate",
    "ResearchAuditReport", "audit_validation_evidence",
    "FEATURE_NAMES", "MLSample", "build_signal_sample", "extract_signal_features",
    "MLResearchMetrics", "MetaFilterModel", "MetaFilterResult", "chronological_train_test",
    "WalkForwardFold", "WalkForwardResult", "walk_forward_backtest", "MLWalkForwardFold", "MLWalkForwardResult", "ml_walk_forward_backtest",
    "MLComparison", "compare_ml_results", "FeatureImportance", "MLStabilityReport", "permutation_feature_importance",
    "REGIMES", "RegimeStats", "classify_regime", "stratify_samples", "FeatureDrift", "MLDriftReport", "analyze_feature_drift",
    "MLBehaviorFold", "MLBehaviorReport", "analyze_ml_behavior",
    "MLEvidencePolicy", "MLEvidenceDecision", "evaluate_ml_evidence_gate",
    "CalibrationBin", "MLModelHealth", "MLModelHealthReport", "analyze_model_health",
    "ModelType", "DeepLearningMetrics", "build_causal_sequences", "train_deep_sequence_model",
    "DeepLearningWalkForwardFold", "DeepLearningWalkForwardResult", "deep_learning_walk_forward_backtest",
]
