from datetime import datetime, time, timedelta, timezone

import pytest

from strategy.execution import ExecutionModel, entry_price, exit_price, simulate_realistic_exit
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


def test_entry_and_exit_helpers_match_long_cost_direction():
    model = ExecutionModel(spread=0.0002, slippage=0.0001)
    assert entry_price(1.1010, "LONG", model) == pytest.approx(1.1012)
    assert exit_price(1.1050, "LONG", model) == pytest.approx(1.1048)


def test_entry_and_exit_helpers_match_short_cost_direction():
    model = ExecutionModel(spread=0.0002, slippage=0.0001)
    assert entry_price(1.0990, "SHORT", model) == pytest.approx(1.0988)
    assert exit_price(1.0950, "SHORT", model) == pytest.approx(1.0952)


def test_execution_model_applies_spread_and_slippage_to_realized_r():
    p = plan()
    bars = [candle(datetime(2026, 1, 1, 1, tzinfo=timezone.utc), 1.1060, 1.1010)]

    result = simulate_realistic_exit(
        p,
        bars,
        ExecutionModel(spread=0.0002, slippage=0.0001, commission=0.0001),
    )

    assert result.outcome == WIN
    assert result.entry > p.entry
    assert result.r_multiple < p.rr


def test_execution_adjusted_risk_plan_can_be_simulated_without_double_entry_cost():
    model = ExecutionModel(spread=0.0002, slippage=0.0001, commission=0.0001)
    raw_plan = plan()
    effective = entry_price(raw_plan.entry, raw_plan.direction, model)
    effective_plan = build_risk_plan(
        raw_plan.direction,
        effective,
        PriceZone(1.0990, 1.1000, SUPPORT, 3),
        stop_buffer=0.0002,
        reward_risk=2.0,
    )
    bars = [candle(datetime(2026, 1, 1, 1, tzinfo=timezone.utc), 1.1070, 1.1010)]

    explicit = simulate_realistic_exit(effective_plan, bars, model, entry_is_effective=True)
    legacy = simulate_realistic_exit(raw_plan, bars, model)

    assert explicit.entry == pytest.approx(legacy.entry)
    assert explicit.stop == pytest.approx(effective_plan.stop)
    assert explicit.target == pytest.approx(effective_plan.target)
    assert explicit.exit_price is not None
    manual_r = (explicit.exit_price - explicit.entry - model.commission) / (explicit.entry - explicit.stop)
    assert explicit.r_multiple == pytest.approx(manual_r)
    assert explicit.r_multiple != pytest.approx(legacy.r_multiple)


def test_higher_friction_does_not_improve_realized_r():
    p = plan()
    bars = [candle(datetime(2026, 1, 1, 1, tzinfo=timezone.utc), 1.1060, 1.1010)]
    low_cost = simulate_realistic_exit(p, bars, ExecutionModel(spread=0.0001, slippage=0.00005, commission=0.0))
    high_cost = simulate_realistic_exit(p, bars, ExecutionModel(spread=0.0004, slippage=0.0002, commission=0.0002))
    assert high_cost.r_multiple <= low_cost.r_multiple


def test_latency_can_delay_exit_detection():
    p = plan()
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = [
        candle(start, 1.1055, 1.1010),
        candle(start + timedelta(minutes=1), 1.1060, 1.1000),
    ]

    result = simulate_realistic_exit(p, bars, ExecutionModel(latency_bars=1))

    assert result.outcome == WIN
    assert result.bars_held == 2


def test_session_filter_requires_time_and_skips_out_of_session_bars():
    p = plan()
    bars = [candle(datetime(2026, 1, 1, 1, tzinfo=timezone.utc), 1.1060, 1.1010)]

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
