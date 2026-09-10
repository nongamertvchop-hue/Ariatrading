from datetime import datetime, timezone

import pytest

from live.data_quality import validate_closed_bars
from live.exposure import risk_budget_allows, summarize_exposure
from live.mt5_executor import PositionSnapshot
from live.position_reconciliation import ReconciliationState, reconcile
from live.runtime_health import HealthState, evaluate_health
from strategy.forex_risk import ForexSymbolContract


def bar(ts, o=1.1, h=1.2, l=1.0, c=1.15):
    return type("Bar", (), {"time": ts, "open": o, "high": h, "low": l, "close": c})()


def test_data_quality_rejects_gap_and_nonfinite():
    t0 = datetime(2026, 9, 10, tzinfo=timezone.utc)
    good = validate_closed_bars([bar(t0), bar(t0.replace(minute=1))], timeframe_seconds=60)
    assert good.ok
    gap = validate_closed_bars([bar(t0), bar(t0.replace(minute=3))], timeframe_seconds=60)
    assert not gap.ok
    assert "gap" in gap.reason
    bad = validate_closed_bars([bar(t0, c=float("nan"))], timeframe_seconds=60)
    assert not bad.ok


def position(ticket, direction, volume=0.1):
    return PositionSnapshot(
        ticket=ticket, symbol="EURUSD", order_type=direction, volume=volume,
        open_price=1.10, sl=1.09 if direction == "BUY" else 1.11, tp=0.0,
        profit=0.0, magic=8808, open_time=datetime(2026, 9, 10, tzinfo=timezone.utc),
    )


def contract():
    return ForexSymbolContract("EURUSD", 5, 0.00001, 1.0, 0.00001, 0.01, 100.0, 0.01)


def test_exposure_tracks_direction_and_risk():
    summary = summarize_exposure([position(1, "BUY"), position(2, "SELL", 0.2)], {"EURUSD": contract()})
    assert summary.total_positions == 2
    assert summary.by_direction["BUY"] == pytest.approx(0.1)
    assert summary.by_direction["SELL"] == pytest.approx(0.2)
    assert summary.risk_cash > 0
    assert not risk_budget_allows(current_risk_cash=90, candidate_risk_cash=20, equity=1000, max_fraction=0.1)[0]


def test_reconciliation_requires_exact_match():
    intent = {"intent_id": "abc", "state": "AMBIGUOUS", "symbol": "EURUSD", "direction": "BUY", "lot_size": 0.1}
    clean = reconcile([intent], [position(1, "BUY")])
    assert clean.state is ReconciliationState.CLEAN or clean.state is ReconciliationState.UNFINISHED

    mismatch = reconcile([intent], [position(1, "SELL")])
    assert mismatch.state is ReconciliationState.MISMATCH


def test_reconciliation_clean_when_no_active_intents():
    report = reconcile([], [position(1, "BUY")])
    assert report.state is ReconciliationState.CLEAN


def test_health_contract_is_explicit():
    assert evaluate_health(heartbeat_age_seconds=1, market_data_age_seconds=1, max_heartbeat_age_seconds=5, max_market_data_age_seconds=5).state is HealthState.HEALTHY
    assert evaluate_health(heartbeat_age_seconds=6, market_data_age_seconds=1, max_heartbeat_age_seconds=5, max_market_data_age_seconds=5).state is HealthState.DEGRADED
    assert evaluate_health(heartbeat_age_seconds=1, market_data_age_seconds=1, max_heartbeat_age_seconds=5, max_market_data_age_seconds=5, blocked=True).state is HealthState.BLOCKED
    assert evaluate_health(heartbeat_age_seconds=1, market_data_age_seconds=1, max_heartbeat_age_seconds=5, max_market_data_age_seconds=5, error=True).state is HealthState.ERROR
