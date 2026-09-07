import pytest

from strategy.engine import EngineSignal, LONG, SHORT, WAIT
from strategy.risk_engine import RiskLimits
from strategy.trade_plan import build_trade_plan


def test_long_trade_plan_uses_signal_entry_and_stop():
    signal = EngineSignal(
        action=LONG,
        reason="confirmed support",
        timeframe="15m",
        entry_reference=1.1010,
        stop_reference=1.0990,
    )

    plan = build_trade_plan(
        signal,
        equity=10_000,
        limits=RiskLimits(risk_per_trade=0.01),
        value_per_price_unit=100_000,
        quantity_step=0.01,
    )

    assert plan.action == LONG
    assert plan.entry == 1.1010
    assert plan.stop == 1.0990
    assert plan.risk.allowed is True
    assert plan.risk.risk_amount <= 100.0 + 1e-9


def test_short_stop_must_be_above_entry():
    signal = EngineSignal(
        action=SHORT,
        reason="confirmed resistance",
        timeframe="15m",
        entry_reference=1.1000,
        stop_reference=1.0990,
    )

    with pytest.raises(ValueError, match="SHORT protective stop must be above entry"):
        build_trade_plan(
            signal,
            equity=10_000,
            limits=RiskLimits(),
        )


def test_wait_signal_cannot_become_trade_plan():
    signal = EngineSignal(
        action=WAIT,
        reason="no setup",
        timeframe="15m",
    )

    with pytest.raises(ValueError, match="only LONG or SHORT"):
        build_trade_plan(signal, equity=10_000, limits=RiskLimits())


def test_risk_limit_can_block_anotherwise_valid_setup():
    signal = EngineSignal(
        action=LONG,
        reason="confirmed support",
        timeframe="15m",
        entry_reference=1.1010,
        stop_reference=1.0990,
    )

    plan = build_trade_plan(
        signal,
        equity=10_000,
        limits=RiskLimits(max_daily_loss=0.03),
        daily_realized_loss=300.0,
        value_per_price_unit=100_000,
    )

    assert plan.risk.allowed is False
    assert plan.risk.quantity == 0.0
