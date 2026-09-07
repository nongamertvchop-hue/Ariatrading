from datetime import datetime, timedelta, timezone

import pytest

from strategy.backtest import run_backtest
from strategy.ml_evaluation import compare_ml_results
from strategy.ml_walk_forward import MLWalkForwardFold, ml_walk_forward_backtest


def make_candles(n=90):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = []
    price = 1.1000
    for i in range(n):
        drift = 0.0008 if i % 2 == 0 else -0.0006
        candles.append({"time": start + timedelta(minutes=i), "open": price,
                        "high": price + 0.0012, "low": price - 0.0012, "close": price + drift})
        price += drift
    return candles


def test_backtest_signal_indices_align_with_signals():
    result = run_backtest(make_candles(), "15m", start_index=10, end_index=40)
    assert len(result.signal_indices) == len(result.signals)
    assert all(10 <= index < 40 for index in result.signal_indices)


def test_ml_walk_forward_records_temporal_and_feature_provenance():
    result = ml_walk_forward_backtest(make_candles(), "15m", history_bars=40, test_bars=20,
                                      step_bars=20, horizon_bars=3)
    assert result.fold_count == 3
    assert len(result.folds) == 3
    assert all(isinstance(fold, MLWalkForwardFold) for fold in result.folds)
    for fold in result.folds:
        assert fold.test_labeled_samples >= 0
        assert fold.train_samples >= 0
        assert fold.train_positive <= fold.train_samples
        assert len(fold.train_feature_sha256) == 64
        assert len(fold.test_feature_sha256) == 64
        if fold.train_samples:
            assert fold.train_last_signal_index is not None
            assert fold.train_last_label_end_index == fold.train_last_signal_index + result.horizon_bars
            assert fold.train_last_label_end_index < fold.test_start
        else:
            assert fold.train_last_signal_index is None
            assert fold.train_last_label_end_index is None
        if fold.test_first_signal_index is not None:
            assert fold.test_start <= fold.test_first_signal_index < fold.test_end
            assert fold.test_first_signal_index <= fold.test_last_signal_index < fold.test_end


def test_ml_comparison_is_descriptive_and_non_optimizing():
    result = ml_walk_forward_backtest(make_candles(), "15m", history_bars=40, test_bars=20,
                                      step_bars=20, horizon_bars=3)
    comparison = compare_ml_results(result.baseline_metrics, result.filtered_metrics,
                                    baseline_trade_count=len(result.baseline_trades),
                                    filtered_trade_count=len(result.filtered_trades))
    assert comparison.trades_removed >= 0
    assert 0.0 <= comparison.trade_reduction_ratio <= 1.0
    assert comparison.filtered_trade_count <= comparison.baseline_trade_count


def test_ml_comparison_rejects_impossible_counts():
    result = ml_walk_forward_backtest(make_candles(), "15m", history_bars=40, test_bars=20,
                                      step_bars=20, horizon_bars=3)
    with pytest.raises(ValueError, match="cannot exceed"):
        compare_ml_results(result.baseline_metrics, result.filtered_metrics,
                           baseline_trade_count=1, filtered_trade_count=2)


def test_ml_walk_forward_validation():
    with pytest.raises(ValueError, match="threshold"):
        ml_walk_forward_backtest(make_candles(), "15m", history_bars=40, test_bars=20, threshold=1.0)
    with pytest.raises(ValueError, match="horizon"):
        ml_walk_forward_backtest(make_candles(), "15m", history_bars=40, test_bars=20, horizon_bars=0)
