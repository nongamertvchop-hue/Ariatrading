from datetime import datetime, timezone

from strategy.engine import EngineSignal, LONG, SHORT, WAIT
from strategy.forecast import DOWN, FLAT, UP, ForecastResult, HorizonForecast
from strategy.realtime_supervisor import ALLOW, supervise


def make_forecast(direction, confidence=0.8):
    probabilities = {
        UP: (0.8, 0.1, 0.1),
        FLAT: (0.1, 0.8, 0.1),
        DOWN: (0.1, 0.1, 0.8),
    }[direction]
    return ForecastResult(
        as_of=datetime(2026, 1, 1, tzinfo=timezone.utc),
        current_close=100.0,
        horizons=(HorizonForecast(1, *probabilities, 0.01 if direction == UP else -0.01, 101.0),),
        scenarios=(),
        confidence=confidence,
    )


def signal(action):
    return EngineSignal(action, "confirmed setup", "1m")


def test_long_is_allowed_when_forecast_agrees():
    decision = supervise(signal(LONG), make_forecast(UP))
    assert decision.action == ALLOW
    assert decision.allowed


def test_short_is_allowed_when_forecast_agrees():
    decision = supervise(signal(SHORT), make_forecast(DOWN))
    assert decision.action == ALLOW
    assert decision.allowed


def test_conflicting_forecast_becomes_wait():
    decision = supervise(signal(LONG), make_forecast(DOWN))
    assert decision.action == WAIT
    assert not decision.allowed
    assert any("conflicts" in reason for reason in decision.reasons)


def test_low_confidence_becomes_wait():
    decision = supervise(signal(LONG), make_forecast(UP, confidence=0.2))
    assert decision.action == WAIT
    assert "confidence" in " ".join(decision.reasons)


def test_strategy_wait_remains_wait():
    decision = supervise(signal(WAIT), make_forecast(UP))
    assert decision.action == WAIT
    assert not decision.allowed


def test_unsafe_protection_becomes_wait():
    candidate = EngineSignal(LONG, "confirmed", "1m", protection="BLOCKED")
    decision = supervise(candidate, make_forecast(UP))
    assert decision.action == WAIT
    assert "protection" in " ".join(decision.reasons)
