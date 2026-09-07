from datetime import datetime, timedelta, timezone

import pytest

from strategy.backtest import run_backtest
from strategy.ml_walk_forward import MLWalkForwardFold, ml_walk_forward_backtest


def make_candles(n=90):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = []
    price = 1.1000
    for i in range(n):
        drift = 0.0008 if i % 2 == 0 else -0.0006
        candles.append(
            {
                "time": start + timedelta(minutes=i),
                "open": price,
                "high": price + 0.0012,
                "low": price - 0.0012,
                "close": price + drift,
            }
        )
        price += drift
    return candles


def test_backtest_signal_indices_align_with_signals():
    result = run_backtest(
        make_candles(),
        "15m",
        start_index=10,
        end_index=40,
    )
    assert len(result.signal_indices) == len(result.signals)
    assert all(10 <= index < 40 for index in result.signal_indices)


def test_ml_walk_forward_runs_without_future_fold_training():
    result = ml_walk_forward_backtest(
        make_candles(),
        "15m",
        history_bars=40,
        test_bars=20,
        step_bars=20,
        horizon_bars=3,
    )

    assert result.fold_count == 3
    assert len(result.folds) == 3
    assert all(isinstance(fold, MLWalkForwardFold) for fold in result.folds)
    for fold in result.folds:
        assert fold.test_labeled_samples >= 0
        assert fold.train_samples >= 0
        assert fold.train_positive <= fold.train_samples


def test_ml_walk_forward_validation():
    with pytest.raises(ValueError, match="threshold"):
        ml_walk_forward_backtest(make_candles(), "15m", history_bars=40, test_bars=20, threshold=1.0)
    with pytest.raises(ValueError, match="horizon"):
        ml_walk_forward_backtest(make_candles(), "15m", history_bars=40, test_bars=20, horizon_bars=0)
