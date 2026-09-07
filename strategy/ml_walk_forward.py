"""Leakage-safe walk-forward evaluation for the ML meta-filter.

The deterministic strategy remains the only source of direction. ML is trained
only on earlier signal-time samples and may only accept/reject an existing
LONG/SHORT signal inside a later out-of-sample window.
"""

from dataclasses import dataclass

from .backtest import (
    ENTRY_TIMING_SIGNAL_REFERENCE,
    BacktestResult,
    run_backtest,
)
from .engine import LONG, SHORT
from .ml_features import MLSample, build_signal_sample, extract_signal_features
from .ml_meta import MetaFilterModel
from .risk import TradeResult
from .validation import ResearchMetrics, evaluate_trades


@dataclass(frozen=True)
class MLWalkForwardFold:
    fold_index: int
    test_start: int
    test_end: int
    baseline: BacktestResult
    filtered: BacktestResult
    train_samples: int
    train_positive: int
    test_labeled_samples: int
    model_trained: bool
    train_last_signal_index: int | None
    train_last_label_end_index: int | None
    test_first_signal_index: int | None
    test_last_signal_index: int | None


@dataclass(frozen=True)
class MLWalkForwardResult:
    timeframe: str
    history_bars: int
    test_bars: int
    step_bars: int
    threshold: float
    horizon_bars: int
    folds: tuple[MLWalkForwardFold, ...]
    baseline_trades: tuple[TradeResult, ...]
    filtered_trades: tuple[TradeResult, ...]
    baseline_metrics: ResearchMetrics
    filtered_metrics: ResearchMetrics

    @property
    def fold_count(self) -> int:
        return len(self.folds)

    @property
    def trained_fold_count(self) -> int:
        return sum(fold.model_trained for fold in self.folds)

    @property
    def filtered_trade_count(self) -> int:
        return len(self.filtered_trades)


def _directional_training_samples(
    candles: list[dict],
    history_result: BacktestResult,
    *,
    horizon_bars: int,
    favorable_move: float,
    train_end: int,
) -> tuple[MLSample, ...]:
    samples: list[MLSample] = []
    for index, signal in zip(history_result.signal_indices, history_result.signals):
        if signal.action not in {LONG, SHORT}:
            continue
        if index + horizon_bars >= train_end:
            continue
        samples.append(
            build_signal_sample(
                candles,
                index,
                signal,
                horizon_bars=horizon_bars,
                favorable_move=favorable_move,
            )
        )
    return tuple(samples)


def ml_walk_forward_backtest(
    candles: list[dict],
    timeframe: str,
    *,
    history_bars: int,
    test_bars: int,
    step_bars: int | None = None,
    reward_risk: float = 2.0,
    max_hold_bars: int = 20,
    mtf_candles_by_timeframe: dict[str, list[dict]] | None = None,
    execution_model=None,
    entry_timing: str = ENTRY_TIMING_SIGNAL_REFERENCE,
    threshold: float = 0.55,
    horizon_bars: int = 3,
    favorable_move: float = 0.0,
) -> MLWalkForwardResult:
    """Compare baseline and ML-filtered results over expanding OOS folds.

    The model for fold N is fitted only from directional signals whose labels
    complete strictly before that fold's test window. The fold also records
    temporal provenance so downstream audits can verify that boundary claim.
    """
    if history_bars < 1:
        raise ValueError("history_bars must be >= 1")
    if test_bars < 1:
        raise ValueError("test_bars must be >= 1")
    if step_bars is None:
        step_bars = test_bars
    if step_bars < test_bars:
        raise ValueError("step_bars must be >= test_bars for non-overlapping folds")
    if not 0 < threshold < 1:
        raise ValueError("threshold must be between 0 and 1")
    if horizon_bars < 1:
        raise ValueError("horizon_bars must be >= 1")
    if favorable_move < 0:
        raise ValueError("favorable_move must be >= 0")
    if len(candles) <= history_bars:
        raise ValueError("candles must contain data after the history window")

    folds: list[MLWalkForwardFold] = []
    baseline_trades: list[TradeResult] = []
    filtered_trades: list[TradeResult] = []

    test_start = history_bars
    fold_index = 1
    while test_start < len(candles):
        test_end = min(test_start + test_bars, len(candles))
        history_result = run_backtest(
            candles,
            timeframe,
            reward_risk=reward_risk,
            max_hold_bars=max_hold_bars,
            mtf_candles_by_timeframe=mtf_candles_by_timeframe,
            execution_model=execution_model,
            start_index=0,
            end_index=test_start,
            entry_timing=entry_timing,
        )
        train_samples = _directional_training_samples(
            candles,
            history_result,
            horizon_bars=horizon_bars,
            favorable_move=favorable_move,
            train_end=test_start,
        )

        baseline = run_backtest(
            candles,
            timeframe,
            reward_risk=reward_risk,
            max_hold_bars=max_hold_bars,
            mtf_candles_by_timeframe=mtf_candles_by_timeframe,
            execution_model=execution_model,
            start_index=test_start,
            end_index=test_end,
            entry_timing=entry_timing,
        )

        model = MetaFilterModel()
        model_trained = False
        if len(train_samples) >= 2 and len({sample.label for sample in train_samples}) == 2:
            model.fit(train_samples)
            model_trained = True

        if model_trained:
            def signal_filter(index: int, signal) -> bool:
                features = extract_signal_features(candles, index, signal)
                return model.approve(features, threshold=threshold)

            filtered = run_backtest(
                candles,
                timeframe,
                reward_risk=reward_risk,
                max_hold_bars=max_hold_bars,
                mtf_candles_by_timeframe=mtf_candles_by_timeframe,
                execution_model=execution_model,
                start_index=test_start,
                end_index=test_end,
                entry_timing=entry_timing,
                signal_filter=signal_filter,
            )
        else:
            filtered = baseline

        test_labeled_samples = sum(
            1
            for index, signal in zip(baseline.signal_indices, baseline.signals)
            if signal.action in {LONG, SHORT} and index + horizon_bars < test_end
        )

        train_last_signal_index = max((sample.index for sample in train_samples), default=None)
        train_last_label_end_index = max(
            (sample.index + horizon_bars for sample in train_samples),
            default=None,
        )
        directional_test_indices = [
            index
            for index, signal in zip(baseline.signal_indices, baseline.signals)
            if signal.action in {LONG, SHORT}
        ]

        fold = MLWalkForwardFold(
            fold_index=fold_index,
            test_start=test_start,
            test_end=test_end,
            baseline=baseline,
            filtered=filtered,
            train_samples=len(train_samples),
            train_positive=sum(sample.label for sample in train_samples),
            test_labeled_samples=test_labeled_samples,
            model_trained=model_trained,
            train_last_signal_index=train_last_signal_index,
            train_last_label_end_index=train_last_label_end_index,
            test_first_signal_index=min(directional_test_indices, default=None),
            test_last_signal_index=max(directional_test_indices, default=None),
        )
        folds.append(fold)
        baseline_trades.extend(baseline.trades)
        filtered_trades.extend(filtered.trades)

        fold_index += 1
        test_start += step_bars

    return MLWalkForwardResult(
        timeframe=timeframe,
        history_bars=history_bars,
        test_bars=test_bars,
        step_bars=step_bars,
        threshold=threshold,
        horizon_bars=horizon_bars,
        folds=tuple(folds),
        baseline_trades=tuple(baseline_trades),
        filtered_trades=tuple(filtered_trades),
        baseline_metrics=evaluate_trades(baseline_trades),
        filtered_metrics=evaluate_trades(filtered_trades),
    )


__all__ = ["MLWalkForwardFold", "MLWalkForwardResult", "ml_walk_forward_backtest"]
