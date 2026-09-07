from datetime import datetime, timedelta, timezone

import pytest

import strategy.backtest as backtest_module
from strategy.backtest import (
    ENTRY_TIMING_NEXT_BAR_OPEN,
    ENTRY_TIMING_SIGNAL_REFERENCE,
    run_all_timeframes,
    run_backtest,
)
from strategy.engine import EngineSignal, LONG
from strategy.execution import ExecutionModel, entry_price
from strategy.levels_v2 import PriceZone, SUPPORT


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


def _patch_simple_long(monkeypatch):
    zone = PriceZone(99.0, 100.0, SUPPORT, 2)

    monkeypatch.setattr(backtest_module, "_latest_zones", lambda history, timeframe: ([zone], []))
    monkeypatch.setattr(
        backtest_module,
        "evaluate_long",
        lambda candles, support, timeframe, mtf=None: EngineSignal(
            LONG,
            "test signal",
            timeframe,
            support,
            entry_reference=100.0,
        ),
    )
    return zone


def test_backtest_entry_timing_next_bar_open_matches_paper_lifecycle(monkeypatch):
    _patch_simple_long(monkeypatch)
    candles = make_candles(40)
    for candle in candles:
        candle["open"] = 100.0
        candle["high"] = 100.5
        candle["low"] = 99.5
        candle["close"] = 100.0
    decision_index = 32
    candles[decision_index + 1]["open"] = 101.0
    candles[decision_index + 2]["high"] = 106.0

    result = run_backtest(
        candles,
        "15m",
        entry_timing=ENTRY_TIMING_NEXT_BAR_OPEN,
        reward_risk=2.0,
        max_hold_bars=5,
    )

    assert result.trades
    assert result.trades[0].entry == 101.0
    assert result.trades[0].outcome == "WIN"
    assert result.trades[0].bars_held == 1


def test_backtest_default_entry_timing_remains_signal_reference(monkeypatch):
    _patch_simple_long(monkeypatch)
    candles = make_candles(40)
    for candle in candles:
        candle["open"] = 101.0
        candle["high"] = 102.5
        candle["low"] = 99.5
        candle["close"] = 100.0

    result = run_backtest(candles, "15m", reward_risk=2.0, max_hold_bars=5)

    assert result.trades
    assert result.trades[0].entry == 100.0


def test_backtest_execution_cost_is_applied_once_before_risk_geometry(monkeypatch):
    zone = _patch_simple_long(monkeypatch)
    candles = make_candles(40)
    for candle in candles:
        candle["open"] = 100.0
        candle["high"] = 100.5
        candle["low"] = 99.5
        candle["close"] = 100.0
    candles[33]["high"] = 106.0
    model = ExecutionModel(spread=0.2, slippage=0.1, commission=0.0, price_digits=2)

    result = run_backtest(
        candles,
        "15m",
        execution_model=model,
        reward_risk=1.0,
        max_hold_bars=5,
    )

    assert result.trades
    trade = result.trades[0]
    expected_entry = entry_price(100.0, LONG, model)
    assert trade.entry == expected_entry
    assert trade.stop == pytest.approx(zone.low - 0.2)
    assert trade.target == pytest.approx(expected_entry + (expected_entry - trade.stop))


def test_backtest_rejects_unknown_entry_timing():
    with pytest.raises(ValueError, match="entry_timing"):
        run_backtest(make_candles(), "15m", entry_timing="same_candle_close")


def test_all_timeframes():
    data = make_candles()
    results = run_all_timeframes({tf: data for tf in ("1m", "5m", "15m", "30m", "1h", "4h", "1D")})
    assert set(results) == {"1m", "5m", "15m", "30m", "1h", "4h", "1D"}
