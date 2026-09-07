import pytest

from strategy.deep_learning_walk_forward import _train_one, deep_learning_walk_forward_backtest
from strategy.ml_features import MLSample
from datetime import datetime, timezone


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


def _sample(index: int, label: int) -> MLSample:
    return MLSample(
        index=index,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        features=(float(index), 1.0),
        label=label,
    )


def test_train_one_does_not_hide_unexpected_value_errors(monkeypatch):
    train = tuple(_sample(i, i % 2) for i in range(8))
    test = (_sample(8, 0), _sample(9, 1))

    def broken_trainer(*args, **kwargs):
        raise ValueError("unexpected data contract violation")

    monkeypatch.setattr("strategy.deep_learning_walk_forward.train_deep_sequence_model", broken_trainer)

    with pytest.raises(ValueError, match="unexpected data contract violation"):
        _train_one(
            train,
            test,
            model_type="lstm",
            sequence_length=8,
            hidden_size=8,
            layers=1,
            heads=2,
            epochs=1,
            learning_rate=1e-3,
            seed=42,
        )
