"""Ariatrading price-action research package.

The package keeps the two core setups stable while exposing consistent
interfaces across strategy, forecast, backtest, execution-cost simulation,
replay, realtime monitoring, paper simulation, deterministic signal identity,
journaling, walk-forward validation, robustness analysis, reproducible research
control, ML meta-filter research, experiment registry, regime diagnostics, ML
feature drift diagnostics, ML OOS behavior diagnostics, ML model health
diagnostics, deep-learning challenger models, deep-learning walk-forward
research, aggregated research evidence, research-gate completeness checks,
execution recovery, paper execution conformance, broker symbol-contract
validation, research provenance, feed integrity, the final system readiness
gate, deterministic historical paper replay, leakage-safe paper outcomes,
paired baseline-vs-MTF paper comparison, paired statistical analysis, and
signal-quality diagnostics.
"""

from .backtest import ENTRY_TIMING_NEXT_BAR_OPEN, ENTRY_TIMING_SIGNAL_REFERENCE, BacktestResult, run_all_timeframes, run_backtest
from .broker_contract import ContractValidation, SymbolContract, validate_order_contract
from .deep_learning import DeepLearningMetrics, ModelType, build_causal_sequences, train_deep_sequence_model
from .deep_learning_walk_forward import DeepLearningWalkForwardFold, DeepLearningWalkForwardResult, deep_learning_walk_forward_backtest
from .engine import EngineSignal, LONG, SHORT, WAIT, evaluate_long, evaluate_short
from .execution import ExecutionModel, entry_price, exit_price
from .execution_audit import AuditEvent, AuditJournal, AuditJournalError
from .execution_recovery import ExecutionRecoveryDecision, ExecutionRecoveryReport, verify_execution_recovery
from .experiment_registry import ExperimentRecord, build_experiment_record
from .feed_integrity import FeedIntegrityReport, validate_feed_batch
from .forecast import ForecastResult, HorizonForecast, ScenarioForecast, forecast
from .journal import JournalEvent, PaperTradeJournal, signal_event_id
from .market_snapshot import MarketSnapshot
from .ml_behavior import MLBehaviorFold, MLBehaviorReport, analyze_ml_behavior
from .ml_drift import FeatureDrift, MLDriftReport, analyze_feature_drift
from .ml_evaluation import MLComparison, compare_ml_results
from .ml_evidence_gate import MLEvidenceDecision, MLEvidencePolicy, evaluate_ml_evidence_gate
from .ml_features import FEATURE_NAMES, MLSample, build_signal_sample, extract_signal_features
from .ml_meta import MLResearchMetrics, MetaFilterModel, MetaFilterResult, chronological_train_test
from .ml_model_comparison import MLChallengerAggregate, MLModelComparison, ModelClassificationMetrics, aggregate_challenger_results, compare_ml_models
from .ml_model_health import CalibrationBin, MLModelHealth, MLModelHealthReport, analyze_model_health
from .ml_stability import FeatureImportance, MLStabilityReport, permutation_feature_importance
from .ml_walk_forward import MLWalkForwardFold, MLWalkForwardResult, ml_walk_forward_backtest
from .mtf_paper_comparison import MtfPaperComparison, PaperComparisonMetrics, compare_mtf_paper_sessions
from .order_persistence import OrderPersistenceError, load_order_state, save_order_state
from .order_state import OrderRecord, OrderState, OrderStateMachine, OrderTransition
from .paired_analysis import DEFAULT_BOOTSTRAP_SAMPLES, DEFAULT_MIN_PAIRS_FOR_CI, PairedRDelta, PairedStatisticalAnalysis, analyze_paired_paper_outcomes
from .paper import CLOSED, OPEN, PaperAccount, PaperPosition, PaperTradingEngine
from .paper_execution_conformance import RecoveryResult, submit_with_recovery
from .paper_outcomes import LOSS as PAPER_LOSS, SKIPPED, UNRESOLVED, WIN as PAPER_WIN, PaperSignalOutcome, label_paper_signals
from .paper_replay import PaperReplayResult, replay_paper_session
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
from .research_provenance import PROVENANCE_SCHEMA_VERSION, ResearchProvenance, build_research_provenance, fingerprint_payload, load_research_provenance, provenance_compatible, save_research_provenance
from .research_runner import ControlledResearchResult, run_controlled_research
from .research_validation import ValidationEvidence, build_validation_evidence
from .regime import REGIMES, RegimeStats, classify_regime, stratify_samples
from .risk_engine import RiskDecision, RiskLimits, evaluate_risk, position_size
from .robustness import RobustnessCase, RobustnessReport, RobustnessScenario, run_robustness_analysis
from .signal_quality import DEFAULT_SCORE_BUCKETS, SignalQualityReport, SignalQualityRow, build_signal_quality_report
from .system_gate import SystemGateDecision, evaluate_system_readiness
from .trade_guard import TradeGuardDecision, evaluate_trade_guard
from .two_setups import TwoSetupResult, evaluate_two_setups
from .walk_forward import WalkForwardFold, WalkForwardResult, walk_forward_backtest

__all__ = [
    "EngineSignal", "LONG", "SHORT", "WAIT", "evaluate_long", "evaluate_short",
    "TwoSetupResult", "evaluate_two_setups", "RiskLimits", "RiskDecision", "position_size", "evaluate_risk",
    "PortfolioRiskLimits", "PortfolioRiskState", "PortfolioRiskDecision", "PortfolioRiskController", "PORTFOLIO_ALLOW", "HALT",
    "PositionSnapshot", "LocalPositionState", "ReconciliationDecision", "reconcile_position", "new_entry_allowed", "FLAT",
    "TradeGuardDecision", "evaluate_trade_guard", "SystemGateDecision", "evaluate_system_readiness",
    "OrderState", "OrderRecord", "OrderTransition", "OrderStateMachine", "OrderPersistenceError", "save_order_state", "load_order_state",
    "AuditEvent", "AuditJournal", "AuditJournalError", "ExecutionRecoveryDecision", "ExecutionRecoveryReport", "verify_execution_recovery", "RecoveryResult", "submit_with_recovery",
    "SymbolContract", "ContractValidation", "validate_order_contract", "FeedIntegrityReport", "validate_feed_batch",
    "PROVENANCE_SCHEMA_VERSION", "ResearchProvenance", "build_research_provenance", "fingerprint_payload", "save_research_provenance", "load_research_provenance", "provenance_compatible",
    "ExecutionModel", "entry_price", "exit_price", "ExperimentRecord", "build_experiment_record", "ForecastResult", "HorizonForecast", "ScenarioForecast", "forecast",
    "JournalEvent", "PaperTradeJournal", "signal_event_id", "MarketSnapshot", "ReplayPoint", "ReplayResult", "replay_forecasts",
    "DataQuality", "RealtimeGuard", "expected_closed_bar_open", "RealtimeReplayResult", "replay_realtime_monitor", "PaperReplayResult", "replay_paper_session",
    "PaperSignalOutcome", "label_paper_signals", "PAPER_WIN", "PAPER_LOSS", "SKIPPED", "UNRESOLVED",
    "PaperComparisonMetrics", "MtfPaperComparison", "compare_mtf_paper_sessions", "DEFAULT_BOOTSTRAP_SAMPLES", "DEFAULT_MIN_PAIRS_FOR_CI", "PairedRDelta", "PairedStatisticalAnalysis", "analyze_paired_paper_outcomes",
    "DEFAULT_SCORE_BUCKETS", "SignalQualityRow", "SignalQualityReport", "build_signal_quality_report",
    "ALLOW", "SupervisorDecision", "supervise", "ResearchReport", "run_research", "BacktestResult", "run_backtest", "run_all_timeframes", "ENTRY_TIMING_SIGNAL_REFERENCE", "ENTRY_TIMING_NEXT_BAR_OPEN",
    "CLOSED", "OPEN", "PaperAccount", "PaperPosition", "PaperTradingEngine", "PaperSessionResult", "PaperSessionRunner", "RobustnessScenario", "RobustnessCase", "RobustnessReport", "run_robustness_analysis",
    "DatasetFingerprint", "ResearchConfig", "ResearchRun", "build_research_run", "config_fingerprint", "fingerprint_candles", "ControlledResearchResult", "run_controlled_research", "ValidationEvidence", "build_validation_evidence", "INCOMPLETE", "READY", "ResearchGateDecision", "evaluate_research_gate",
    "ResearchAuditReport", "audit_validation_evidence", "FEATURE_NAMES", "MLSample", "build_signal_sample", "extract_signal_features", "MLResearchMetrics", "MetaFilterModel", "MetaFilterResult", "chronological_train_test",
    "WalkForwardFold", "WalkForwardResult", "walk_forward_backtest", "MLWalkForwardFold", "MLWalkForwardResult", "ml_walk_forward_backtest", "MLComparison", "compare_ml_results", "FeatureImportance", "MLStabilityReport", "permutation_feature_importance",
    "REGIMES", "RegimeStats", "classify_regime", "stratify_samples", "FeatureDrift", "MLDriftReport", "analyze_feature_drift", "MLBehaviorFold", "MLBehaviorReport", "analyze_ml_behavior",
    "MLEvidencePolicy", "MLEvidenceDecision", "evaluate_ml_evidence_gate", "CalibrationBin", "MLModelHealth", "MLModelHealthReport", "analyze_model_health", "ModelType", "DeepLearningMetrics", "build_causal_sequences", "train_deep_sequence_model",
    "DeepLearningWalkForwardFold", "DeepLearningWalkForwardResult", "deep_learning_walk_forward_backtest", "ModelClassificationMetrics", "MLModelComparison", "MLChallengerAggregate", "compare_ml_models", "aggregate_challenger_results",
]
