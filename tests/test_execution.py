from datetime import datetime, time, timedelta, timezone

import pytest

from strategy.execution import ExecutionModel, simulate_realistic_exit
from strategy.levels_v2 import PriceZone, SUPPORT
from strategy.risk import WIN, build_risk_plan


def plan():
    return build_risk_plan(
        "LONG",
        1.1010,
        PriceZone(1.0990, 1.1000, SUPPORT, 3),
        stop_buffer=0.0002,
        reward_risk=2.0,
    )


def candle(ts, high, low):
    return {"time": ts, "open": low, "high": high, "low": low, "close": high}


def test_execution_model_applies_spread_and_slippage_to_realized_r():
    p = plan()
    bars = [candle(datetime(2026, 1, 1, 1, tzinfo=timezone.utc), 1.1055, 1.1010)]

    result = simulate_realistic_exit(
        p,
        bars,
        ExecutionModel(spread=0.0002, slippage=0.0001, commission=0.0001),
    )

    assert result.outcome == WIN
    assert result.entry > p.entry
    assert result.r_multiple < p.rr


def test_latency_can_delay_exit_detection():
    p = plan()
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = [
        candle(start, 1.1055, 1.1010),
        candle(start + timedelta(minutes=1), 1.1015, 1.1000),
    ]

    result = simulate_realistic_exit(p, bars, ExecutionModel(latency_bars=1))

    assert result.outcome == WIN
    assert result.bars_held == 2


def test_session_filter_requires_time_and_skips_out_of_session_bars():
    p = plan()
    bars = [candle(datetime(2026, 1, 1, 1, tzinfo=timezone.utc), 1.1055, 1.1010)]

    result = simulate_realistic_exit(
        p,
        bars,
        ExecutionModel(session_start=time(9, 0), session_end=time(17, 0)),
    )

    assert result.outcome == "OPEN"


def test_execution_model_validates_configuration():
    with pytest.raises(ValueError):
        ExecutionModel(spread=-0.1)
    with pytest.raises(ValueError):
        ExecutionModel(latency_bars=-1)
    with pytest.raises(ValueError):
        ExecutionModel(session_start=time(9, 0))
