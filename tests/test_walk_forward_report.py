from strategy.backtest import BacktestResult
from strategy.risk import LOSS, WIN, TradeResult
from strategy.walk_forward_report import build_walk_forward_report


def make_result(trades):
    return BacktestResult(
        timeframe="15m",
        candles_tested=5,
        long_signals=2,
        short_signals=0,
        wait_signals=3,
        trades=tuple(trades),
        signals=(),
        signal_indices=(),
    )


def test_report_aggregates_oos_folds_in_order():
    fold1 = make_result([
        TradeResult("LONG", 100.0, 99.0, 102.0, 102.0, WIN, 2, 2.0),
    ])
    fold2 = make_result([
        TradeResult("LONG", 100.0, 99.0, 102.0, 99.0, LOSS, 1, -1.0),
    ])

    report = build_walk_forward_report(
        "15m",
        history_bars=20,
        test_bars=5,
        step_bars=5,
        folds=((1, 20, fold1), (2, 25, fold2)),
    )

    assert report.fold_count == 2
    assert report.aggregate.closed_trades == 2
    assert report.aggregate.net_r == 1.0
    assert report.aggregate.expectancy_r == 0.5
    assert report.positive_net_r_folds == 1
    assert report.profitable_fold_ratio == 0.5
    assert report.folds[0].test_start == 20
    assert report.folds[0].test_end == 25
    assert report.folds[1].test_start == 25


def test_report_rejects_non_chronological_folds():
    result = make_result([])
    try:
        build_walk_forward_report(
            "15m",
            history_bars=20,
            test_bars=5,
            step_bars=5,
            folds=((2, 25, result), (1, 20, result)),
        )
    except ValueError as exc:
        assert "chronological" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_report_rejects_overlapping_window_configuration():
    try:
        build_walk_forward_report(
            "15m",
            history_bars=20,
            test_bars=10,
            step_bars=5,
            folds=(),
        )
    except ValueError as exc:
        assert "invalid walk-forward window" in str(exc)
    else:
        raise AssertionError("expected ValueError")
