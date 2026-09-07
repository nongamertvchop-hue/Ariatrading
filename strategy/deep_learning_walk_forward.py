"""Leakage-safe fold-by-fold LSTM/Transformer walk-forward research.

Deep learning remains a challenger/meta-filter. The deterministic strategy is
run first and supplies the LONG/SHORT signal samples. Each fold trains only on
completed labels from the expanding history, then evaluates later OOS samples.
No fold may update a model from a later fold, and no final OOS winner selection
is performed here.

PyTorch is optional; the orchestration imports it only when a fold actually
needs model training.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from .backtest import ENTRY_TIMING_SIGNAL_REFERENCE, BacktestResult, run_backtest
from .deep_learning import DeepLearningMetrics, ModelType, train_deep_sequence_model
from .engine import LONG, SHORT
from .ml_features import MLSample, build_signal_sample
from .risk import TradeResult
from .validation import ResearchMetrics, evaluate_trades


@dataclass(frozen=True)
class DeepLearningWalkForwardFold:
    fold_index: int
    test_start: int
    test_end: int
    baseline: BacktestResult
    train_samples: int
    train_positive: int
    test_samples: int
    train_last_signal_index: int | None
    train_last_label_end_index: int | None
    test_first_signal_index: int | None
    test_last_signal_index: int | None
    feature_width: int
    train_feature_sha256: str
    test_feature_sha256: str
    lstm_metrics: DeepLearningMetrics | None
    transformer_metrics: DeepLearningMetrics | None

    @property
    def models_trained(self) -> int:
        return sum(metric is not None for metric in (self.lstm_metrics, self.transformer_metrics))


@dataclass(frozen=True)
class DeepLearningWalkForwardResult:
    timeframe: str
    history_bars: int
    test_bars: int
    step_bars: int
    sequence_length: int
    horizon_bars: int
    folds: tuple[DeepLearningWalkForwardFold, ...]
    baseline_trades: tuple[TradeResult, ...]
    baseline_metrics: ResearchMetrics

    @property
    def fold_count(self) -> int:
        return len(self.folds)

    @property
    def lstm_fold_count(self) -> int:
        return sum(fold.lstm_metrics is not None for fold in self.folds)

    @property
    def transformer_fold_count(self) -> int:
        return sum(fold.transformer_metrics is not None for fold in self.folds)


def _fingerprint(samples: tuple[MLSample, ...]) -> str:
    rows = [
        {
            "index": sample.index,
            "timestamp": sample.timestamp.isoformat() if hasattr(sample.timestamp, "isoformat") else sample.timestamp,
            "features": [format(float(value), ".17g") for value in sample.features],
            "label": sample.label,
        }
        for sample in samples
    ]
    canonical = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def _training_samples(
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


def _test_samples(
    candles: list[dict],
    result: BacktestResult,
    *,
    test_end: int,
    horizon_bars: int,
    favorable_move: float,
) -> tuple[MLSample, ...]:
    samples: list[MLSample] = []
    for index, signal in zip(result.signal_indices, result.signals):
        if signal.action not in {LONG, SHORT}:
            continue
        # The test label must be fully observable inside this fold. A label
        # reaching beyond test_end would contaminate the fold boundary.
        if index + horizon_bars >= test_end:
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


def _train_one(
    train_samples: tuple[MLSample, ...],
    test_samples: tuple[MLSample, ...],
    *,
    model_type: ModelType,
    sequence_length: int,
    hidden_size: int,
    layers: int,
    heads: int,
    epochs: int,
    learning_rate: float,
    seed: int,
) -> DeepLearningMetrics | None:
    if len(train_samples) < sequence_length:
        return None
    if len({sample.label for sample in train_samples}) != 2:
        return None
    if len(test_samples) < 1:
        return None

    # Preflight checks above cover the expected "not enough data" cases.
    # Remaining ValueError exceptions are configuration or data-contract
    # violations and must surface instead of silently producing an incomplete
    # research record.
    _, metrics = train_deep_sequence_model(
        train_samples,
        test_samples,
        model_type=model_type,
        sequence_length=sequence_length,
        hidden_size=hidden_size,
        layers=layers,
        heads=heads,
        epochs=epochs,
        learning_rate=learning_rate,
        seed=seed,
    )
    return metrics


def deep_learning_walk_forward_backtest(
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
    sequence_length: int = 8,
    horizon_bars: int = 3,
    favorable_move: float = 0.0,
    hidden_size: int = 32,
    layers: int = 1,
    heads: int = 4,
    epochs: int = 20,
    learning_rate: float = 1e-3,
    seed: int = 42,
) -> DeepLearningWalkForwardResult:
    """Run chronological OOS folds for both LSTM and Transformer challengers."""
    if history_bars < 1 or test_bars < 1:
        raise ValueError("history_bars and test_bars must be >= 1")
    if step_bars is None:
        step_bars = test_bars
    if step_bars < test_bars:
        raise ValueError("step_bars must be >= test_bars for non-overlapping folds")
    if sequence_length < 2:
        raise ValueError("sequence_length must be >= 2")
    if horizon_bars < 1:
        raise ValueError("horizon_bars must be >= 1")
    if favorable_move < 0:
        raise ValueError("favorable_move must be >= 0")
    if hidden_size < 1 or layers < 1 or heads < 1 or epochs < 1 or learning_rate <= 0:
        raise ValueError("invalid deep-learning configuration")
    if len(candles) <= history_bars:
        raise ValueError("candles must contain data after the history window")

    folds: list[DeepLearningWalkForwardFold] = []
    baseline_trades: list[TradeResult] = []
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

        train_samples = _training_samples(
            candles,
            history_result,
            horizon_bars=horizon_bars,
            favorable_move=favorable_move,
            train_end=test_start,
        )
        test_samples = _test_samples(
            candles,
            baseline,
            test_end=test_end,
            horizon_bars=horizon_bars,
            favorable_move=favorable_move,
        )

        common_kwargs = {
            "train_samples": train_samples,
            "test_samples": test_samples,
            "sequence_length": sequence_length,
            "hidden_size": hidden_size,
            "layers": layers,
            "heads": heads,
            "epochs": epochs,
            "learning_rate": learning_rate,
        }
        lstm_metrics = _train_one(model_type="lstm", seed=seed, **common_kwargs)
        transformer_metrics = _train_one(model_type="transformer", seed=seed, **common_kwargs)

        directional_train_indices = [sample.index for sample in train_samples]
        directional_test_indices = [sample.index for sample in test_samples]
        fold = DeepLearningWalkForwardFold(
            fold_index=fold_index,
            test_start=test_start,
            test_end=test_end,
            baseline=baseline,
            train_samples=len(train_samples),
            train_positive=sum(sample.label for sample in train_samples),
            test_samples=len(test_samples),
            train_last_signal_index=max(directional_train_indices, default=None),
            train_last_label_end_index=max((sample.index + horizon_bars for sample in train_samples), default=None),
            test_first_signal_index=min(directional_test_indices, default=None),
            test_last_signal_index=max(directional_test_indices, default=None),
            feature_width=len(train_samples[0].features) if train_samples else 0,
            train_feature_sha256=_fingerprint(train_samples),
            test_feature_sha256=_fingerprint(test_samples),
            lstm_metrics=lstm_metrics,
            transformer_metrics=transformer_metrics,
        )
        folds.append(fold)
        baseline_trades.extend(baseline.trades)
        fold_index += 1
        test_start += step_bars

    return DeepLearningWalkForwardResult(
        timeframe=timeframe,
        history_bars=history_bars,
        test_bars=test_bars,
        step_bars=step_bars,
        sequence_length=sequence_length,
        horizon_bars=horizon_bars,
        folds=tuple(folds),
        baseline_trades=tuple(baseline_trades),
        baseline_metrics=evaluate_trades(baseline_trades),
    )


__all__ = [
    "DeepLearningWalkForwardFold",
    "DeepLearningWalkForwardResult",
    "deep_learning_walk_forward_backtest",
]
