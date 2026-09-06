from strategy.execution import ExecutionModel
from strategy.pipeline import run_research


def candle(i: int, close: float = 1.1) -> dict:
    from datetime import datetime, timedelta, timezone
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=i)
    return {"time": ts, "open": close, "high": close + 0.0005, "low": close - 0.0005, "close": close}


def test_integrated_pipeline_returns_consistent_research_report():
    report = run_research(
        [candle(i) for i in range(40)],
        "1m",
        execution_model=ExecutionModel(spread=0.0001, slippage=0.00005),
        bootstrap_iterations=100,
    )
    assert report.backtest.timeframe == "1m"
    assert report.metrics.trade_count == len(report.backtest.trades)
    assert len(report.split.train) + len(report.split.validation) + len(report.split.test) == len(report.backtest.trades)
    assert report.expectancy_ci[0] <= report.expectancy_ci[1]


def test_integrated_pipeline_accepts_empty_history():
    report = run_research([], "1h", bootstrap_iterations=100)
    assert report.backtest.candles_tested == 0
    assert report.metrics.trade_count == 0
    assert report.expectancy_ci == (0.0, 0.0)
