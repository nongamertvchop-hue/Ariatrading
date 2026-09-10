from datetime import datetime, time, timezone

import pytest

from strategy.forex_conditions import (
    ForexConditionDecision,
    ForexSessionConfig,
    check_forex_conditions,
    get_current_session,
)


def test_session_detection_london_and_ny():
    # 14:00 UTC is both London and New York overlap
    dt = datetime(2026, 9, 10, 14, 0, tzinfo=timezone.utc)
    session = get_current_session(dt)
    assert "LONDON" in session
    assert "NEW_YORK" in session


def test_session_detection_off_hours():
    # 21:15 UTC is off hours (NY closed, Sydney starting around 21:00 or off)
    dt = datetime(2026, 9, 10, 20, 0, tzinfo=timezone.utc)
    session = get_current_session(dt)
    assert "NEW_YORK" in session


def test_rollover_window_lockout():
    cfg = ForexSessionConfig()
    # 22:00 UTC is inside default rollover window (21:30 - 22:30 UTC)
    rollover_time = datetime(2026, 9, 10, 22, 0, tzinfo=timezone.utc)

    decision = check_forex_conditions(
        symbol="EURUSD",
        bid=1.10000,
        ask=1.10010,
        point=0.00001,
        timestamp=rollover_time,
        config=cfg,
    )
    assert not decision.allowed
    assert decision.is_rollover
    assert "rollover protection window" in decision.reason


def test_session_filter_enforcement():
    cfg = ForexSessionConfig(
        allowed_start_utc=time(7, 0),
        allowed_end_utc=time(21, 0),
        enforce_session_filter=True,
    )
    # 03:00 UTC is outside allowed hours (Asian session)
    night_time = datetime(2026, 9, 10, 3, 0, tzinfo=timezone.utc)

    decision = check_forex_conditions(
        symbol="EURUSD",
        bid=1.10000,
        ask=1.10010,
        point=0.00001,
        timestamp=night_time,
        config=cfg,
    )
    assert not decision.allowed
    assert "outside allowed trading hours" in decision.reason


def test_spread_guard_normal_passes():
    cfg = ForexSessionConfig(default_max_spread_points=20.0)
    # Spread is 12 points (1.2 pips on 5-digit)
    dt = datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)

    decision = check_forex_conditions(
        symbol="EURUSD",
        bid=1.10000,
        ask=1.10012,
        point=0.00001,
        timestamp=dt,
        config=cfg,
    )
    assert decision.allowed
    assert pytest.approx(decision.spread_points) == 12.0


def test_spread_guard_spike_rejects():
    cfg = ForexSessionConfig(default_max_spread_points=20.0)
    # Spread is 35 points (3.5 pips on 5-digit)
    dt = datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)

    decision = check_forex_conditions(
        symbol="EURUSD",
        bid=1.10000,
        ask=1.10035,
        point=0.00001,
        timestamp=dt,
        config=cfg,
    )
    assert not decision.allowed
    assert pytest.approx(decision.spread_points) == 35.0
    assert "exceeds maximum allowed" in decision.reason


def test_crossed_book_rejects():
    dt = datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)
    decision = check_forex_conditions(
        symbol="EURUSD",
        bid=1.10020,
        ask=1.10010,
        point=0.00001,
        timestamp=dt,
    )
    assert not decision.allowed
    assert "crossed book" in decision.reason
