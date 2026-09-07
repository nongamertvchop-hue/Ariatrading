from datetime import datetime, timezone

from strategy.engine import EngineSignal, LONG, WAIT
from strategy.portfolio_risk import ALLOW as PORTFOLIO_ALLOW, HALT, PortfolioRiskDecision
from strategy.risk_engine import RiskDecision
from strategy.realtime_guard import DataQuality
from strategy.trade_guard import ALLOW, DENY, evaluate_trade_guard


_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _signal(action=LONG):
    return EngineSignal(action=action, reason="confirmed", timeframe="15m")


def _quality(ok=True):
    return DataQuality(ok=ok, reason="ok" if ok else "stale feed", latest_time=_NOW)


def _portfolio(allowed=True):
    return PortfolioRiskDecision(
        PORTFOLIO_ALLOW if allowed else HALT,
        allowed,
        "ok" if allowed else "halted",
        0.0,
        0.0,
        0,
    )


def _risk(allowed=True, quantity=10.0):
    return RiskDecision(allowed, "ok" if allowed else "blocked", quantity if allowed else 0.0, 100.0 if allowed else 0.0, 0.01 if allowed else 0.0)


def test_all_hard_guards_pass():
    decision = evaluate_trade_guard(
        signal=_signal(),
        data_quality=_quality(),
        portfolio_risk=_portfolio(),
        risk=_risk(),
    )
    assert decision.action == ALLOW
    assert decision.allowed
    assert decision.quantity == 10.0


def test_wait_is_always_denied():
    decision = evaluate_trade_guard(
        signal=_signal(WAIT),
        data_quality=_quality(),
        portfolio_risk=_portfolio(),
        risk=_risk(),
    )
    assert decision.action == DENY
    assert not decision.allowed


def test_bad_data_blocks_trade():
    decision = evaluate_trade_guard(
        signal=_signal(),
        data_quality=_quality(False),
        portfolio_risk=_portfolio(),
        risk=_risk(),
    )
    assert not decision.allowed
    assert "data quality" in decision.reason


def test_portfolio_halt_blocks_trade():
    decision = evaluate_trade_guard(
        signal=_signal(),
        data_quality=_quality(),
        portfolio_risk=_portfolio(False),
        risk=_risk(),
    )
    assert not decision.allowed
    assert "portfolio risk" in decision.reason


def test_existing_position_blocks_trade():
    decision = evaluate_trade_guard(
        signal=_signal(),
        data_quality=_quality(),
        portfolio_risk=_portfolio(),
        risk=_risk(),
        position_open=True,
    )
    assert not decision.allowed


def test_risk_rejection_blocks_trade():
    decision = evaluate_trade_guard(
        signal=_signal(),
        data_quality=_quality(),
        portfolio_risk=_portfolio(),
        risk=_risk(False),
    )
    assert not decision.allowed
    assert "trade risk" in decision.reason


def test_non_positive_quantity_fails_closed():
    decision = evaluate_trade_guard(
        signal=_signal(),
        data_quality=_quality(),
        portfolio_risk=_portfolio(),
        risk=_risk(True, 0.0),
    )
    assert not decision.allowed


def test_guard_does_not_modify_signal_direction():
    signal = _signal(LONG)
    decision = evaluate_trade_guard(
        signal=signal,
        data_quality=_quality(),
        portfolio_risk=_portfolio(),
        risk=_risk(),
    )
    assert decision.allowed
    assert signal.action == LONG
