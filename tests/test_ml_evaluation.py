from strategy.ml_evaluation import MLComparison, compare_ml_results
from strategy.validation import ResearchMetrics


def metrics(*, net_r, expectancy_r, win_rate, max_drawdown_r):
    return ResearchMetrics(
        trade_count=10,
        closed_trades=10,
        wins=5,
        losses=5,
        win_rate=win_rate,
        net_r=net_r,
        expectancy_r=expectancy_r,
        profit_factor=1.0,
        max_drawdown_r=max_drawdown_r,
        average_win_r=1.0,
        average_loss_r=-1.0,
    )


def test_compare_ml_results_calculates_deltas():
    baseline = metrics(net_r=2.0, expectancy_r=0.2, win_rate=0.5, max_drawdown_r=3.0)
    filtered = metrics(net_r=3.0, expectancy_r=0.4, win_rate=0.6, max_drawdown_r=2.0)

    result = compare_ml_results(
        baseline,
        filtered,
        baseline_trade_count=10,
        filtered_trade_count=7,
    )

    assert isinstance(result, MLComparison)
    assert result.trades_removed == 3
    assert result.trade_reduction_ratio == 0.3
    assert result.net_r_delta == 1.0
    assert result.expectancy_r_delta == 0.2
    assert result.win_rate_delta == 0.1
    assert result.drawdown_r_delta == -1.0
    assert result.expectancy_improved
    assert result.drawdown_improved


def test_compare_ml_results_rejects_invalid_trade_counts():
    baseline = metrics(net_r=0.0, expectancy_r=0.0, win_rate=0.0, max_drawdown_r=0.0)
    filtered = baseline

    try:
        compare_ml_results(baseline, filtered, baseline_trade_count=2, filtered_trade_count=3)
    except ValueError as exc:
        assert "filtered_trade_count" in str(exc)
    else:
        raise AssertionError("expected ValueError")
