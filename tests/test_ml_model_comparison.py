from datetime import datetime, timezone

import pytest

from strategy.deep_learning import DeepLearningMetrics
from strategy.ml_features import FEATURE_NAMES, MLSample
from strategy.ml_model_comparison import aggregate_challenger_results, compare_ml_models


def _sample(index, label):
    features = [0.0] * len(FEATURE_NAMES)
    features[0] = float(1 if index % 2 else -1)
    features[1] = float(index % 3) / 2.0
    return MLSample(
        index=index,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        features=tuple(features),
        label=label,
    )


def _train_samples():
    return [_sample(i, i % 2) for i in range(8)]


def _test_samples():
    return [_sample(i, i % 2) for i in range(8, 12)]


def test_comparison_rejects_overlapping_train_and_test():
    with pytest.raises(ValueError, match="strictly precede"):
        compare_ml_models(_train_samples(), [_sample(7, 1), _sample(8, 0)])


def test_comparison_requires_both_training_classes():
    train = [_sample(i, 1) for i in range(8)]
    with pytest.raises(ValueError, match="both label classes"):
        compare_ml_models(train, _test_samples())


def test_comparison_uses_same_fixed_oos_window(monkeypatch):
    calls = []

    def fake_trainer(train_samples, test_samples, *, model_type, **kwargs):
        calls.append((model_type, len(train_samples), len(test_samples), kwargs["sequence_length"], kwargs["seed"]))
        return object(), DeepLearningMetrics(
            model_type=model_type,
            train_samples=8,
            test_samples=4,
            sequence_length=kwargs["sequence_length"],
            feature_count=len(FEATURE_NAMES),
            accuracy=0.75 if model_type == "lstm" else 0.50,
            positive_precision=0.60,
            positive_recall=0.70,
            final_train_loss=0.4,
        )

    monkeypatch.setattr("strategy.ml_model_comparison.train_deep_sequence_model", fake_trainer)
    result = compare_ml_models(_train_samples(), _test_samples(), sequence_length=4, seed=123)

    assert [call[0] for call in calls] == ["lstm", "transformer"]
    assert all(call[1:] == (8, 4, 4, 123) for call in calls)
    assert result.lstm.test_samples == result.transformer.test_samples == result.baseline.test_samples
    assert result.accuracy_delta_lstm_vs_baseline == pytest.approx(result.lstm.accuracy - result.baseline.accuracy)
    assert result.accuracy_delta_transformer_vs_baseline == pytest.approx(
        result.transformer.accuracy - result.baseline.accuracy
    )


def test_aggregate_reports_all_models_without_selection():
    def metrics(name, accuracy):
        return type("M", (), {
            "accuracy": accuracy,
            "positive_precision": 0.5,
            "positive_recall": 0.6,
        })()

    from strategy.ml_model_comparison import MLModelComparison

    comparisons = (
        MLModelComparison(metrics("baseline", 0.5), metrics("lstm", 0.6), metrics("transformer", 0.7)),
        MLModelComparison(metrics("baseline", 0.7), metrics("lstm", 0.5), metrics("transformer", 0.6)),
    )
    result = aggregate_challenger_results(comparisons)

    assert [item.model_name for item in result] == ["baseline", "lstm", "transformer"]
    assert [item.mean_accuracy for item in result] == [pytest.approx(0.6), pytest.approx(0.55), pytest.approx(0.65)]
    assert result[0].std_accuracy > 0
