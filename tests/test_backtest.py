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


def test_all_timeframes():
    data = make_candles()
    results = run_all_timeframes({tf: data for tf in ("1m", "5m", "15m", "30m", "1h", "4h", "1D")})
    assert set(results) == {"1m", "5m", "15m", "30m", "1h", "4h", "1D"}
