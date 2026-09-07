from datetime import datetime, timedelta, timezone

import pytest

from strategy.execution import ExecutionModel
from strategy.robustness import RobustnessScenario, run_robustness_analysis
from strategy.walk_forward import walk_forward_backtest


def make_candles(n=50):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    data = []
    price = 1.1000
    for i in range(n):
        move = 0.0002 if i % 2 == 0 else -0.0001
        data.append(
            {
                "time": start + timedelta(minutes=i),
                "open": price,
                "high": price + 0.0010,
                "low": price - 0.0010,
                "close": price + move,
            }
        )
        price += move
    return data


def test_robustness_runs_each_scenario_independently():
    candles = make_candles()
    base_model = ExecutionModel()
    stressed_model = ExecutionModel(spread=0.0002, slippage=0.0001, commission=0.00005, latency_bars=1)
    scenarios = (
        RobustnessScenario("base", base_model),
        RobustnessScenario("stressed", stressed_model),
    )

    report = run_robustness_analysis(
        candles,
        "15m",
        scenarios=scenarios,
        history_bars=20,
        test_bars=10,
    )

    expected = walk_forward_backtest(
        candles,
        "15m",
        history_bars=20,
        test_bars=10,
        execution_model=base_model,
    )

    assert report.timeframe == "15m"
    assert report.scenario_names == ("base", "stressed")
    assert report.case_count == 2
    assert report.cases[0].walk_forward == expected
    assert report.net_r_range == (
        min(case.metrics.net_r for case in report.cases),
        max(case.metrics.net_r for case in report.cases),
    )


def test_robustness_rejects_duplicate_scenario_names():
    scenario = RobustnessScenario("base", ExecutionModel())
    with pytest.raises(ValueError, match="duplicate scenario name"):
        run_robustness_analysis(
            make_candles(),
            "15m",
            scenarios=(scenario, scenario),
            history_bars=20,
            test_bars=10,
        )


def test_robustness_rejects_blank_scenario_name():
    with pytest.raises(ValueError, match="scenario name must be non-empty"):
        RobustnessScenario("   ", ExecutionModel())


def test_empty_robustness_report_has_zero_ranges():
    report = run_robustness_analysis(
        make_candles(),
        "15m",
        scenarios=(),
        history_bars=20,
        test_bars=10,
    )

    assert report.case_count == 0
    assert report.scenario_names == ()
    assert report.net_r_range == (0.0, 0.0)
    assert report.expectancy_r_range == (0.0, 0.0)
