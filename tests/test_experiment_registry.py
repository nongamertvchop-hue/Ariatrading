from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from strategy.experiment_registry import ExperimentRecord, build_experiment_record
from strategy.ml_stability import FeatureImportance, MLStabilityReport
from strategy.research_control import DatasetFingerprint, ResearchConfig, ResearchRun
from strategy.regime import RegimeStats
from strategy.validation import evaluate_trades


def _controlled():
    config = ResearchConfig(
        symbol="EURUSD",
        timeframe="1h",
        history_bars=20,
        test_bars=10,
        step_bars=10,
    )
    control = ResearchRun(
        config=config,
        config_sha256="config-sha",
        dataset=DatasetFingerprint(
            sha256="dataset-sha",
            candle_count=40,
            first_time="2026-01-01T00:00:00+00:00",
            last_time="2026-01-02T15:00:00+00:00",
        ),
    )
    walk_forward = SimpleNamespace(
        timeframe="1h",
        history_bars=20,
        test_bars=10,
        step_bars=10,
    )
    return SimpleNamespace(control=control, walk_forward=walk_forward)


def _ml_result():
    metrics = evaluate_trades([])
    return SimpleNamespace(
        timeframe="1h",
        history_bars=20,
        test_bars=10,
        step_bars=10,
        threshold=0.55,
        horizon_bars=3,
        folds=(),
        baseline_trades=(),
        filtered_trades=(),
        baseline_metrics=metrics,
        filtered_metrics=metrics,
        fold_count=0,
        trained_fold_count=0,
    )


def test_experiment_fingerprint_is_independent_of_creation_time():
    first = build_experiment_record(
        _controlled(),
        _ml_result(),
        model_params={"b": 2, "a": 1},
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    second = build_experiment_record(
        _controlled(),
        _ml_result(),
        model_params={"a": 1, "b": 2},
        created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    assert isinstance(first, ExperimentRecord)
    assert first.experiment_sha256 == second.experiment_sha256
    assert first.created_at != second.created_at


def test_experiment_json_is_stable_and_contains_dataset_fingerprint():
    record = build_experiment_record(
        _controlled(),
        _ml_result(),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    payload = record.to_json()

    assert payload == record.to_json()
    assert '"dataset"' in payload
    assert '"dataset-sha"' in payload
    assert record.to_dict()["ml"]["threshold"] == 0.55


def test_experiment_requires_timezone_aware_creation_time():
    with pytest.raises(ValueError, match="timezone-aware"):
        build_experiment_record(
            _controlled(),
            _ml_result(),
            created_at=datetime(2026, 1, 1),
        )


def test_validation_diagnostics_are_embedded_in_fingerprint_and_json():
    regime = (RegimeStats(regime="BULLISH", samples=4, positive=3),)
    stability = MLStabilityReport(
        sample_count=4,
        feature_count=2,
        baseline_accuracy=0.75,
        importance=(FeatureImportance(0, 0.25, 0.0, 3), FeatureImportance(1, 0.0, 0.0, 3)),
    )
    first = build_experiment_record(
        _controlled(),
        _ml_result(),
        regime_stats=regime,
        stability_report=stability,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    second = build_experiment_record(
        _controlled(),
        _ml_result(),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    validation = first.to_dict()["validation"]
    assert validation["regime"]["stats"][0]["positive_rate"] == 0.75
    assert validation["stability"]["sample_count"] == 4
    assert first.experiment_sha256 != second.experiment_sha256
    assert '"validation"' in first.to_json()
