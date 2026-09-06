from datetime import datetime, timedelta, timezone

import pytest

from strategy.walk_forward import walk_forward_backtest


def make_candles(n=60):
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


def test_walk_forward_creates_non_overlapping_test_windows():
    result = walk_forward_backtest(
        make_candles(50),
        "15m",
        history_bars=20,
        test_bars=10,
    )

    assert result.fold_count == 3
    assert [(f.test_start, f.test_end) for f in result.folds] == [
        (20, 30),
        (30, 40),
        (40, 50),
    ]
    assert result.total_test_bars == 30


def test_walk_forward_uses_expanding_history_but_caps_exits_at_test_boundary():
    result = walk_forward_backtest(
        make_candles(45),
        "15m",
        history_bars=20,
        test_bars=10,
        step_bars=5,
    )

    assert result.fold_count == 5
    assert [(f.test_start, f.test_end) for f in result.folds] == [
        (20, 30),
        (25, 35),
        (30, 40),
        (35, 45),
        (40, 45),
    ]
    for fold in result.folds:
        assert fold.backtest.candles_tested == fold.test_end - fold.test_start
        for trade in fold.backtest.trades:
            assert trade.bars_held <= fold.test_end - fold.test_start


def test_walk_forward_is_deterministic():
    candles = make_candles()
    first = walk_forward_backtest(candles, "15m", history_bars=20, test_bars=10)
    second = walk_forward_backtest(candles, "15m", history_bars=20, test_bars=10)

    assert first == second


def test_walk_forward_rejects_invalid_window_configuration():
    candles = make_candles()
    with pytest.raises(ValueError):
        walk_forward_backtest(candles, "15m", history_bars=0, test_bars=10)
    with pytest.raises(ValueError):
        walk_forward_backtest(candles, "15m", history_bars=20, test_bars=0)
    with pytest.raises(ValueError):
        walk_forward_backtest(candles, "15m", history_bars=100, test_bars=10)
