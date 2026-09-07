from types import SimpleNamespace

import pytest

from strategy.ml_behavior import analyze_ml_behavior


def _metrics(net_r, expectancy_r, win_rate, max_drawdown_r):
    return SimpleNamespace(
        net_r=net_r,
        expectancy_r=expectancy_r,
        win_rate=win_rate,
        max_drawdown_r=max_drawdown_r,
    )


def _backtest(metrics, trade_count):
    return SimpleNamespace(metrics=metrics, trades=tuple(range(trade_count)), net_r=metrics.net_r,
                           expectancy_r=metrics.expectancy_r, win_rate=metrics.win_rate,
                           max_drawdown_r=metrics.max_drawdown_r)


def _result():
    fold1 = SimpleNamespace(
        fold_index=1,
        model_trained=True,
        baseline=_backtest(_metrics(2.0, 0.5, 0.5, -1.0), 4),
        filtered=_backtest(_metrics(3.0, 0.75, 0.75, -0.5), 3),
    )
    fold2 = SimpleNamespace(
        fold_index=2,
        model_trained=True,
        baseline=_backtest(_metrics(-1.0, -0.25, 0.25, -2.0), 4),
        filtered=_backtest(_metrics(-0.5, -0.25, 0.5, -1.5), 2),
    )
    return SimpleNamespace(folds=(fold1, fold2), trained_fold_count=2)


def test_behavior_is_fold_level_and_descriptive():
    report = analyze_ml_behavior(_result())

    assert report.fold_count == 2
    assert report.trained_fold_count == 2
    assert report.folds[0].filtered_trades == 3
    assert report.folds[0].trade_reduction_ratio == pytest.approx(0.25)
    assert report.folds[0].net_r_delta == pytest.approx(1.0)
    assert report.mean_net_r_delta == pytest.approx(0.75)
    assert report.mean_expectancy_r_delta == pytest.approx(0.125)


def test_behavior_rejects_impossible_filtered_trade_count():
    result = _result()
    result.folds[0].filtered = _backtest(_metrics(3.0, 0.75, 0.75, -0.5), 5)

    with pytest.raises(ValueError, match="cannot exceed"):
        analyze_ml_behavior(result)
