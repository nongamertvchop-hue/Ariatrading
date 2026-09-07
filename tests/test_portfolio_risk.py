import pytest
from datetime import datetime, timezone

from strategy.portfolio_risk import ALLOW, HALT, PortfolioRiskController, PortfolioRiskLimits


def test_daily_loss_latches_halt():
    controller = PortfolioRiskController(10_000, PortfolioRiskLimits(max_daily_loss_fraction=0.03))
    controller.update_equity(9_700)
    decision = controller.evaluate()
    assert decision.action == HALT
    assert not decision.allowed


def test_realized_loss_is_effective_before_next_equity_snapshot():
    controller = PortfolioRiskController(10_000, PortfolioRiskLimits(max_daily_loss_fraction=0.03))
    controller.record_closed_trade(-300)
    decision = controller.evaluate()
    assert decision.action == HALT
    assert not decision.allowed
    assert decision.daily_loss_fraction == pytest.approx(0.03)


def test_realized_and_equity_loss_are_not_double_counted():
    controller = PortfolioRiskController(10_000, PortfolioRiskLimits(max_daily_loss_fraction=0.05))
    controller.record_closed_trade(-200)
    controller.update_equity(9_850)
    assert controller.state.daily_realized_loss == pytest.approx(200)
    assert controller.evaluate().daily_loss_fraction == pytest.approx(0.02)


def test_drawdown_uses_peak_equity():
    controller = PortfolioRiskController(10_000, PortfolioRiskLimits(max_drawdown_fraction=0.10))
    controller.update_equity(12_000)
    controller.update_equity(10_801)
    decision = controller.evaluate()
    assert decision.action == ALLOW
    assert decision.drawdown_fraction == pytest.approx(1_199 / 12_000)


def test_consecutive_losses_trigger_halt():
    controller = PortfolioRiskController(10_000, PortfolioRiskLimits(max_consecutive_losses=2))
    controller.record_closed_trade(-50)
    controller.record_closed_trade(-25)
    decision = controller.evaluate()
    assert not decision.allowed
    assert decision.consecutive_losses == 2


def test_default_consecutive_loss_limit_is_five():
    assert PortfolioRiskLimits().max_consecutive_losses == 5


def test_win_resets_consecutive_losses_before_limit():
    controller = PortfolioRiskController(10_000, PortfolioRiskLimits(max_consecutive_losses=3))
    controller.record_closed_trade(-50)
    controller.record_closed_trade(-25)
    controller.record_closed_trade(100)
    assert controller.state.consecutive_losses == 0
    assert controller.evaluate().allowed


def test_weekly_drawdown_circuit_breaker_latches():
    controller = PortfolioRiskController(
        10_000,
        PortfolioRiskLimits(max_weekly_drawdown_fraction=0.05, max_daily_loss_fraction=1.0),
    )
    monday = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)
    controller.update_equity(12_000, timestamp=monday)
    controller.update_equity(11_399, timestamp=datetime(2026, 9, 8, 12, tzinfo=timezone.utc))
    decision = controller.evaluate()
    assert decision.action == HALT
    assert not decision.allowed
    assert decision.weekly_drawdown_fraction == pytest.approx(601 / 12_000)


def test_realized_weekly_loss_also_trips_weekly_breaker():
    controller = PortfolioRiskController(
        10_000,
        PortfolioRiskLimits(
            max_daily_loss_fraction=1.0,
            max_consecutive_losses=100,
            max_weekly_drawdown_fraction=0.05,
        ),
    )
    controller.record_closed_trade(-500, timestamp=datetime(2026, 9, 7, 12, tzinfo=timezone.utc))
    decision = controller.evaluate()
    assert decision.action == HALT
    assert decision.weekly_drawdown_fraction == pytest.approx(0.05)


def test_halt_is_latched_until_session_reset():
    controller = PortfolioRiskController(10_000, PortfolioRiskLimits(max_consecutive_losses=1))
    controller.record_closed_trade(-50)
    assert not controller.evaluate().allowed
    controller.update_equity(10_000)
    assert not controller.evaluate().allowed
    controller.reset_session(9_950)
    assert controller.evaluate().allowed


def test_invalid_initial_equity_is_rejected():
    with pytest.raises(ValueError):
        PortfolioRiskController(0)
