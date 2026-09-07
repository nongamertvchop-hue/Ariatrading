from types import SimpleNamespace

import pytest

from strategy.ml_stability import FeatureImportance, MLStabilityReport
from strategy.research_validation import build_validation_evidence
from strategy.regime import RegimeStats
from strategy.validation import ResearchMetrics


def _metrics():
    return ResearchMetrics(
        trade_count=2,
        closed_trades=2,
        wins=1,
        losses=1,
        win_rate=0.5,
        net_r=1.0,
        expectancy_r=0.5,
        profit_factor=2.0,
        max_drawdown_r=-1.0,
        average_win_r=2.0,
        average_loss_r=-1.0,
    )


def _controlled(timeframe="1h"):
    backtest = SimpleNamespace(candles_tested=10, trades=())
    fold = SimpleNamespace(
        fold_index=1,
        history_start=0,
        test_start=10,
        test_end=20,
        backtest=backtest,
    )
    walk_forward = SimpleNamespace(
        timeframe=timeframe,
        fold_count=1,
        folds=(fold,),
        metrics=_metrics(),
    )
    control = SimpleNamespace(
        config_sha256="config-sha",
        dataset=SimpleNamespace(sha256="dataset-sha"),
    )
    return SimpleNamespace(control=control, walk_forward=walk_forward)


def _ml_result(timeframe="1h"):
    fold = SimpleNamespace(
        fold_index=1,
        train_samples=10,
        train_positive=5,
        test_labeled_samples=4,
        model_trained=True,
    )
    return SimpleNamespace(
        timeframe=timeframe,
        fold_count=1,
        trained_fold_count=1,
        threshold=0.55,
        horizon_bars=3,
        baseline_metrics=_metrics(),
        filtered_metrics=_metrics(),
        baseline_trades=(1, 2),
        filtered_trades=(1,),
        folds=(fold,),
    )


def test_validation_evidence_is_deterministic_and_serializable():
    stability = MLStabilityReport(
        sample_count=10,
        feature_count=2,
        baseline_accuracy=0.8,
        importance=(FeatureImportance(0, 0.2, 0.01, 3),),
    )
    regimes = (RegimeStats("BULLISH", 6, 4), RegimeStats("RANGE", 4, 2))

    first = build_validation_evidence(
        _controlled(),
        _ml_result(),
        regime_stats=regimes,
        stability=stability,
    )
    second = build_validation_evidence(
        _controlled(),
        _ml_result(),
        regime_stats=regimes,
        stability=stability,
    )

    assert first.evidence_sha256 == second.evidence_sha256
    assert first.dataset_sha256 == "dataset-sha"
    assert first.config_sha256 == "config-sha"
    assert first.stability["sample_count"] == 10
    assert first.robustness is None
    assert '"evidence_sha256"' in first.to_json()


def test_validation_evidence_rejects_timeframe_mismatch():
    with pytest.raises(ValueError, match="same timeframe"):
        build_validation_evidence(_controlled("1h"), _ml_result("4h"))


def test_validation_evidence_rejects_invalid_regime_name():
    with pytest.raises(ValueError, match="regime name"):
        build_validation_evidence(
            _controlled(),
            _ml_result(),
            regime_stats=(RegimeStats("", 1, 0),),
        )
