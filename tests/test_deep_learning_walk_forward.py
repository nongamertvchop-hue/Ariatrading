import json
import pytest

from datetime import datetime, timezone

from strategy.backtest import BacktestResult
from strategy.deep_learning_walk_forward import _fingerprint, _train_one, deep_learning_walk_forward_backtest
from strategy.ml_features import MLSample
from strategy.research_provenance import load_research_provenance


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


def _sample(index: int, label: int, feature_value: float | None = None) -> MLSample:
    value = float(index) if feature_value is None else feature_value
    return MLSample(
        index=index,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        features=(value, 1.0),
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


def test_deep_learning_feature_fingerprint_excludes_labels():
    samples = tuple(_sample(i, i % 2) for i in range(3))
    relabeled = tuple(_sample(i, (i + 1) % 2) for i in range(3))
    changed_features = tuple(_sample(i, i % 2, feature_value=float(i) + 0.5) for i in range(3))

    assert _fingerprint(samples) == _fingerprint(relabeled)
    assert _fingerprint(samples) != _fingerprint(changed_features)


def test_deep_learning_walk_forward_persists_provenance_without_training(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "strategy.deep_learning_walk_forward.run_backtest",
        lambda *args, **kwargs: BacktestResult(
            timeframe=args[1],
            candles_tested=10,
            long_signals=0,
            short_signals=0,
            wait_signals=10,
            trades=(),
            signals=(),
            signal_indices=(),
        ),
    )

    candles = [
        {
            "time": f"2026-01-{index + 1:02d}T00:00:00Z",
            "open": 1.0,
            "high": 1.1,
            "low": 0.9,
            "close": 1.0,
        }
        for index in range(20)
    ]
    path = tmp_path / "dl-provenance.json"

    result = deep_learning_walk_forward_backtest(
        candles,
        "1h",
        history_bars=10,
        test_bars=5,
        provenance_path=str(path),
    )

    assert result.fold_count == 2
    provenance = load_research_provenance(path)
    assert provenance.model_name == "lstm+transformer_walk_forward"
    assert provenance.code_version == "0.13.3"
    assert provenance.fingerprint
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 1


def test_deep_learning_walk_forward_rejects_empty_provenance_code_version():
    candles = [
        {"time": str(i), "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0}
        for i in range(12)
    ]
    with pytest.raises(ValueError, match="code_version"):
        deep_learning_walk_forward_backtest(
            candles,
            "1h",
            history_bars=10,
            test_bars=2,
            code_version="",
        )
