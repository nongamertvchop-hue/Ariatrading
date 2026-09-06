from datetime import datetime, timezone

from strategy.engine import EngineSignal, LONG, SHORT, WAIT
from strategy.execution import ExecutionModel
from strategy.levels_v2 import PriceZone, SUPPORT, RESISTANCE
from strategy.paper import CLOSED, OPEN, PaperTradingEngine


def dt(minute: int) -> datetime:
    return datetime(2026, 1, 1, 0, minute, tzinfo=timezone.utc)


def support() -> PriceZone:
    return PriceZone(SUPPORT, 99.0, 100.0, 3, (dt(0), dt(1), dt(2)))


def resistance() -> PriceZone:
    return PriceZone(RESISTANCE, 100.0, 101.0, 3, (dt(0), dt(1), dt(2)))


def test_wait_is_ignored():
    engine = PaperTradingEngine()
    signal = EngineSignal(WAIT, "unclear", "1m")
    assert engine.open_from_signal(signal, signal_time=dt(1), entry_time=dt(2), entry_price=100.0) is None
    assert engine.position is None


def test_signal_must_open_on_later_bar():
    engine = PaperTradingEngine()
    signal = EngineSignal(LONG, "confirmed", "1m", zone=support())
    try:
        engine.open_from_signal(signal, signal_time=dt(1), entry_time=dt(1), entry_price=101.0)
    except ValueError as exc:
        assert "later" in str(exc)
    else:
        raise AssertionError("same-bar entry must be rejected")


def test_naive_signal_time_is_rejected():
    engine = PaperTradingEngine()
    signal = EngineSignal(LONG, "confirmed", "1m", zone=support())
    try:
        engine.open_from_signal(
            signal,
            signal_time=datetime(2026, 1, 1, 0, 1),
            entry_time=dt(2),
            entry_price=101.0,
        )
    except ValueError as exc:
        assert "timezone-aware" in str(exc)
    else:
        raise AssertionError("naive timestamps must be rejected")


def test_long_position_closes_at_target():
    engine = PaperTradingEngine(reward_risk=2.0)
    signal = EngineSignal(LONG, "confirmed", "1m", zone=support())
    position = engine.open_from_signal(signal, signal_time=dt(1), entry_time=dt(2), entry_price=101.0)
    assert position is not None
    assert position.status == OPEN
    closed = engine.on_bar({"time": dt(3), "high": 105.0, "low": 101.0})
    assert closed is not None
    assert closed.status == CLOSED
    assert closed.outcome == "WIN"
    assert closed.r_multiple == 2.0
    assert engine.account.wins == 1


def test_long_stop_wins_conservative_priority_when_both_hit():
    engine = PaperTradingEngine(reward_risk=2.0)
    signal = EngineSignal(LONG, "confirmed", "1m", zone=support())
    engine.open_from_signal(signal, signal_time=dt(1), entry_time=dt(2), entry_price=101.0)
    closed = engine.on_bar({"time": dt(3), "high": 105.0, "low": 98.0})
    assert closed is not None
    assert closed.outcome == "LOSS"
    assert closed.r_multiple == -1.0


def test_short_position_closes_at_target():
    engine = PaperTradingEngine(reward_risk=2.0)
    signal = EngineSignal(SHORT, "confirmed", "1m", zone=resistance())
    position = engine.open_from_signal(signal, signal_time=dt(1), entry_time=dt(2), entry_price=99.0)
    assert position is not None
    closed = engine.on_bar({"time": dt(3), "high": 99.0, "low": 93.0})
    assert closed is not None
    assert closed.outcome == "WIN"
    assert closed.r_multiple == 2.0


def test_short_stop_wins_conservative_priority_when_both_hit():
    engine = PaperTradingEngine(reward_risk=2.0)
    signal = EngineSignal(SHORT, "confirmed", "1m", zone=resistance())
    engine.open_from_signal(signal, signal_time=dt(1), entry_time=dt(2), entry_price=99.0)
    closed = engine.on_bar({"time": dt(3), "high": 102.0, "low": 95.0})
    assert closed is not None
    assert closed.outcome == "LOSS"
    assert closed.r_multiple == -1.0


def test_unsafe_or_breakout_signal_is_not_opened():
    engine = PaperTradingEngine()
    unsafe = EngineSignal(LONG, "blocked", "1m", zone=support(), protection="BLOCKED")
    breakout = EngineSignal(LONG, "breakout", "1m", zone=support(), breakout_state="TRUE_BREAKOUT")
    assert engine.open_from_signal(unsafe, signal_time=dt(1), entry_time=dt(2), entry_price=101.0) is None
    assert engine.open_from_signal(breakout, signal_time=dt(1), entry_time=dt(2), entry_price=101.0) is None


def test_second_position_is_not_opened_while_one_is_active():
    engine = PaperTradingEngine()
    signal = EngineSignal(LONG, "confirmed", "1m", zone=support())
    assert engine.open_from_signal(signal, signal_time=dt(1), entry_time=dt(2), entry_price=101.0) is not None
    assert engine.open_from_signal(signal, signal_time=dt(3), entry_time=dt(4), entry_price=101.0) is None


def test_execution_costs_are_applied_before_risk_geometry():
    model = ExecutionModel(spread=0.2, slippage=0.1, commission=0.0, price_digits=2)
    engine = PaperTradingEngine(reward_risk=1.0, execution_model=model)
    signal = EngineSignal(LONG, "confirmed", "1m", zone=support())
    position = engine.open_from_signal(signal, signal_time=dt(1), entry_time=dt(2), entry_price=101.0)
    assert position is not None
    assert position.entry_price == 101.2
    assert position.risk_distance == 2.2
    assert position.target == 103.4
    closed = engine.on_bar({"time": dt(3), "high": 104.0, "low": 101.0})
    assert closed is not None
    assert closed.outcome == "WIN"
    assert closed.r_multiple == (103.2 - 101.2) / 2.2
