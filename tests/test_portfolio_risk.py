import pytest

from strategy.portfolio_risk import ALLOW, HALT, PortfolioRiskController, PortfolioRiskLimits


def test_daily_loss_latches_halt():
    controller = PortfolioRiskController(
        10_000,
        PortfolioRiskLimits(max_daily_loss_fraction=0.03),
    )
    controller.update_equity(9_700)
    decision = controller.evaluate()
    assert decision.action == HALT
    assert not decision.allowed


def test_drawdown_uses_peak_equity():
    controller = PortfolioRiskController(
        10_000,
        PortfolioRiskLimits(max_drawdown_fraction=0.10),
    )
    controller.update_equity(12_000)
    controller.update_equity(10_800)
    decision = controller.evaluate()
    assert decision.action == ALLOW
    assert decision.drawdown_fraction == pytest.approx(1_200 / 12_000)


def test_consecutive_losses_trigger_halt():
    controller = PortfolioRiskController(
        10_000,
        PortfolioRiskLimits(max_consecutive_losses=2),
    )
    controller.record_closed_trade(-50)
    controller.record_closed_trade(-25)
    decision = controller.evaluate()
    assert not decision.allowed
    assert decision.consecutive_losses == 2


def test_win_resets_consecutive_losses_before_limit():
    controller = PortfolioRiskController(
        10_000,
        PortfolioRiskLimits(max_consecutive_losses=3),
    )
    controller.record_closed_trade(-50)
    controller.record_closed_trade(-25)
    controller.record_closed_trade(100)
    assert controller.state.consecutive_losses == 0
    assert controller.evaluate().allowed


def test_halt_is_latched_until_session_reset():
    controller = PortfolioRiskController(
        10_000,
        PortfolioRiskLimits(max_consecutive_losses=1),
    )
    controller.record_closed_trade(-50)
    assert not controller.evaluate().allowed
    controller.update_equity(10_000)
    assert not controller.evaluate().allowed
    controller.reset_session(9_950)
    assert controller.evaluate().allowed


def test_invalid_initial_equity_is_rejected():
    with pytest.raises(ValueError):
        PortfolioRiskController(0)
