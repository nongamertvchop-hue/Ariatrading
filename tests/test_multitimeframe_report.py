from strategy.backtest import BacktestResult
from strategy.multitimeframe_report import build_multitimeframe_report
from strategy.risk import LOSS, WIN, TradeResult
from strategy.walk_forward import WalkForwardFold, WalkForwardResult
from strategy.validation import evaluate_trades


def make_result(timeframe: str, fold_values: tuple[float, ...]) -> WalkForwardResult:
    folds = []
    trades = []
    for index, value in enumerate(fold_values, start=1):
        outcome = WIN if value > 0 else LOSS if value < 0 else "OPEN"
        trade = TradeResult(
            "LONG",
            100.0,
            99.0,
            102.0,
            102.0 if value > 0 else 99.0 if value < 0 else None,
            outcome,
            1,
            value,
        )
        trades.append(trade)
        backtest = BacktestResult(
            timeframe=timeframe,
            candles_tested=5,
            long_signals=1,
            short_signals=0,
            wait_signals=4,
            trades=(trade,),
            signals=(),
            signal_indices=(),
        )
        folds.append(
            WalkForwardFold(
                fold_index=index,
                history_start=0,
                test_start=(index - 1) * 5,
                test_end=index * 5,
                backtest=backtest,
                metrics=evaluate_trades((trade,)),
            )
        )

    return WalkForwardResult(
        timeframe=timeframe,
        history_bars=20,
        test_bars=5,
        step_bars=5,
        folds=tuple(folds),
        trades=tuple(trades),
        metrics=evaluate_trades(tuple(trades)),
    )


def test_multitimeframe_report_is_deterministic_and_sorted():
    results = {
        "1h": make_result("1h", (2.0, -1.0)),
        "15m": make_result("15m", (-1.0, -1.0)),
        "1m": make_result("1m", (1.0, 1.0)),
    }

    report = build_multitimeframe_report(results)

    assert [row.timeframe for row in report.rows] == ["1h", "15m", "1m"]
    assert report.timeframe_count == 3
    assert report.common_history_bars == 20
    assert report.common_test_bars == 5
    assert report.common_step_bars == 5
    assert report.consistently_profitable_timeframes == 2


def test_multitimeframe_report_requires_matching_mapping_keys():
    result = make_result("15m", (1.0,))

    try:
        build_multitimeframe_report({"1h": result})
    except ValueError as exc:
        assert "does not match result timeframe" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_multitimeframe_report_can_enforce_full_timeframe_set():
    results = {"1m": make_result("1m", (1.0,))}

    try:
        build_multitimeframe_report(
            results,
            expected_timeframes=("1m", "5m"),
        )
    except ValueError as exc:
        assert "timeframe set mismatch" in str(exc)
    else:
        raise AssertionError("expected ValueError")
