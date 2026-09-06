import pytest

from strategy.risk import LOSS, OPEN, WIN, TradeResult
from strategy.validation import bootstrap_expectancy_ci, chronological_split, evaluate_trades


def trade(r, outcome):
    return TradeResult("LONG", 1.0, 0.9, 1.2, 1.0 + r * 0.1 if outcome != OPEN else None, outcome, 1, r)


def test_evaluate_trades_reports_core_metrics():
    metrics = evaluate_trades([
        trade(2.0, WIN),
        trade(-1.0, LOSS),
        trade(0.0, OPEN),
    ])

    assert metrics.trade_count == 3
    assert metrics.closed_trades == 2
    assert metrics.wins == 1
    assert metrics.losses == 1
    assert metrics.win_rate == 0.5
    assert metrics.net_r == 1.0
    assert metrics.expectancy_r == 0.5
    assert metrics.profit_factor == 2.0
    assert metrics.max_drawdown_r == 1.0


def test_chronological_split_preserves_order():
    trades = [trade(float(i), WIN) for i in range(10)]
    split = chronological_split(trades, train_ratio=0.6, validation_ratio=0.2)

    assert len(split.train) == 6
    assert len(split.validation) == 2
    assert len(split.test) == 2
    assert split.train[0].r_multiple == 0.0
    assert split.validation[0].r_multiple == 6.0
    assert split.test[0].r_multiple == 8.0


def test_chronological_split_rejects_invalid_ratios():
    with pytest.raises(ValueError):
        chronological_split([], train_ratio=0.8, validation_ratio=0.3)


def test_bootstrap_ci_is_deterministic_with_seed():
    trades = [trade(2.0, WIN), trade(-1.0, LOSS)] * 10
    first = bootstrap_expectancy_ci(trades, iterations=500, seed=123)
    second = bootstrap_expectancy_ci(trades, iterations=500, seed=123)
    assert first == second
    assert first[0] <= first[1]
