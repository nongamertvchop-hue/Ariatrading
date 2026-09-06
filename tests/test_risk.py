import pytest

from strategy.levels_v2 import PriceZone, RESISTANCE, SUPPORT
from strategy.risk import LOSS, OPEN, WIN, build_risk_plan, simulate_exit


def test_long_risk_plan_and_target():
    zone = PriceZone(1.0990, 1.1000, SUPPORT, 3)
    plan = build_risk_plan("LONG", 1.1010, zone, 0.0002, 2.0)
    assert plan.stop == pytest.approx(1.0988)
    assert plan.risk_distance == pytest.approx(0.0022)
    assert plan.target == pytest.approx(1.1054)


def test_short_risk_plan_and_target():
    zone = PriceZone(1.1090, 1.1100, RESISTANCE, 3)
    plan = build_risk_plan("SHORT", 1.1080, zone, 0.0002, 2.0)
    assert plan.stop == pytest.approx(1.1102)
    assert plan.target == pytest.approx(1.1036)


def test_long_target_win():
    zone = PriceZone(1.0990, 1.1000, SUPPORT, 3)
    plan = build_risk_plan("LONG", 1.1010, zone, 0.0002, 2.0)
    result = simulate_exit(plan, [{"open": 1.1010, "high": 1.1055, "low": 1.1005, "close": 1.1050}])
    assert result.outcome == WIN
    assert result.r_multiple == pytest.approx(2.0)


def test_long_stop_loss():
    zone = PriceZone(1.0990, 1.1000, SUPPORT, 3)
    plan = build_risk_plan("LONG", 1.1010, zone, 0.0002, 2.0)
    result = simulate_exit(plan, [{"open": 1.1010, "high": 1.1020, "low": 1.0980, "close": 1.0990}])
    assert result.outcome == LOSS
    assert result.r_multiple == pytest.approx(-1.0)


def test_both_stop_and_target_same_candle_is_conservative_loss():
    zone = PriceZone(1.0990, 1.1000, SUPPORT, 3)
    plan = build_risk_plan("LONG", 1.1010, zone, 0.0002, 2.0)
    result = simulate_exit(plan, [{"open": 1.1010, "high": 1.1060, "low": 1.0980, "close": 1.1020}])
    assert result.outcome == LOSS


def test_open_when_neither_level_is_hit():
    zone = PriceZone(1.0990, 1.1000, SUPPORT, 3)
    plan = build_risk_plan("LONG", 1.1010, zone, 0.0002, 2.0)
    result = simulate_exit(plan, [{"open": 1.1010, "high": 1.1030, "low": 1.1005, "close": 1.1020}])
    assert result.outcome == OPEN
