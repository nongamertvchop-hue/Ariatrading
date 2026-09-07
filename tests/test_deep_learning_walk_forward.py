import pytest

from strategy.deep_learning_walk_forward import deep_learning_walk_forward_backtest


def test_deep_learning_walk_forward_validates_fold_geometry():
    candles = [
        {"open": 100 + i, "high": 101 + i, "low": 99 + i, "close": 100 + i}
        for i in range(12)
    ]
    with pytest.raises(ValueError, match="step_bars"):
        deep_learning_walk_forward_backtest(
            candles,
            "5m",
            history_bars=5,
            test_bars=3,
            step_bars=2,
        )


def test_deep_learning_walk_forward_requires_history_before_test():
    candles = [
        {"open": 100 + i, "high": 101 + i, "low": 99 + i, "close": 100 + i}
        for i in range(5)
    ]
    with pytest.raises(ValueError, match="after the history window"):
        deep_learning_walk_forward_backtest(
            candles,
            "5m",
            history_bars=5,
            test_bars=1,
        )


def test_deep_learning_walk_forward_is_optional_when_torch_is_absent():
    pytest.importorskip("torch")
