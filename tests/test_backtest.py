from datetime import datetime, timedelta, timezone

import pytest

from strategy.backtest import run_all_timeframes, run_backtest


def make_candles(n=40):
    data = []
    price = 1.1000
    for i in range(n):
        move = 0.0002 if i % 2 == 0 else -0.0001
        data.append(
            {
                "open": price,
                "high": price + 0.0010,
                "low": price - 0.0010,
                "close": price + move,
            }
        )
        price += move
    return data


def make_timestamped_candles(n=40, minutes=15):
    data = make_candles(n)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        {**candle, "time": start + timedelta(minutes=minutes * i)}
        for i, candle in enumerate(data)
    ]


def test_empty_backtest():
    result = run_backtest([], "1m")
    assert result.candles_tested == 0
    assert result.total_directional_signals == 0


def test_backtest_is_sequential_and_returns_one_result_per_test_candle():
    data = make_candles()
    result = run_backtest(data, "15m")
    assert result.candles_tested > 0
    assert result.candles_tested == len(result.signals)
    assert result.long_signals + result.short_signals + result.wait_signals == result.candles_tested


def test_backtest_mtf_requires_timestamps_instead_of_guessing_alignment():
    data = make_candles()
    with pytest.raises(ValueError, match="MTF backtest requires timezone-aware datetime candle times"):
        run_backtest(data, "15m", mtf_candles_by_timeframe={"15m": data, "1h": data})


def test_backtest_accepts_timestamped_mtf_data():
    entry = make_timestamped_candles(40, 15)
    higher = make_timestamped_candles(10, 60)

    result = run_backtest(
        entry,
        "15m",
        mtf_candles_by_timeframe={"15m": entry, "1h": higher},
    )

    assert result.candles_tested > 0
    assert result.candles_tested == len(result.signals)


def test_all_timeframes():
    data = make_candles()
    results = run_all_timeframes({tf: data for tf in ("1m", "5m", "15m", "30m", "1h", "4h", "1D")})
    assert set(results) == {"1m", "5m", "15m", "30m", "1h", "4h", "1D"}
