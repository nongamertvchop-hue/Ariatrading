import pytest

from strategy.risk_engine import RiskLimits, evaluate_risk, position_size


def test_position_size_stays_within_risk_budget():
    quantity = position_size(10_000, 1.1000, 1.0950, 0.01)
    assert quantity == pytest.approx(20_000.0)


def test_quantity_step_is_floored_not_rounded_up():
    quantity = position_size(
        10_000,
        100.0,
        99.0,
        0.01,
        value_per_price_unit=1.0,
        quantity_step=3.0,
    )
    assert quantity == 99.0


def test_daily_loss_limit_blocks_new_trade():
    decision = evaluate_risk(
        equity=10_000,
        entry=1.1,
        stop=1.095,
        limits=RiskLimits(max_daily_loss=0.03),
        daily_realized_loss=300,
    )
    assert not decision.allowed
    assert decision.quantity == 0.0


def test_open_risk_limit_caps_requested_size():
    decision = evaluate_risk(
        equity=10_000,
        entry=100.0,
        stop=99.0,
        limits=RiskLimits(risk_per_trade=0.02, max_open_risk=0.03),
        open_risk_amount=200,
    )
    assert decision.allowed
    assert decision.risk_amount <= 100.0 + 1e-12


def test_max_positions_blocks_new_trade():
    decision = evaluate_risk(
        equity=10_000,
        entry=100.0,
        stop=99.0,
        limits=RiskLimits(max_positions=1),
        open_positions=1,
    )
    assert not decision.allowed


def test_invalid_entry_stop_is_rejected():
    with pytest.raises(ValueError):
        position_size(10_000, 100.0, 100.0, 0.01)


def test_min_quantity_is_a_hard_limit():
    decision = evaluate_risk(
        equity=1000.0,
        entry=100.0,
        stop=99.0,
        limits=RiskLimits(min_quantity=11.0),
        quantity_step=2.0,
    )
    assert not decision.allowed
    assert "minimum quantity" in decision.reason


def test_minimum_quantity_survives_max_quantity_cap():
    decision = evaluate_risk(
        equity=1000.0,
        entry=100.0,
        stop=99.0,
        limits=RiskLimits(min_quantity=2.0, max_quantity=2.5),
        quantity_step=1.0,
    )
    assert decision.allowed
    assert decision.quantity == pytest.approx(2.0)


def test_max_quantity_cap_can_become_below_minimum_after_step_floor():
    decision = evaluate_risk(
        equity=1000.0,
        entry=100.0,
        stop=99.0,
        limits=RiskLimits(min_quantity=2.0, max_quantity=2.5),
        quantity_step=3.0,
    )
    assert not decision.allowed
    assert "minimum quantity" in decision.reason or "minimum step" in decision.reason
