import pytest

from strategy.position_reconciliation import (
    ALLOW,
    FLAT,
    HALT,
    LONG,
    LocalPositionState,
    PositionSnapshot,
    new_entry_allowed,
    reconcile_position,
)


def broker(direction=LONG, quantity=1.0, position_id="p1", symbol="EURUSD"):
    return PositionSnapshot(symbol, direction, quantity, position_id)


def local(direction=LONG, quantity=1.0, position_id="p1", symbol="EURUSD"):
    return LocalPositionState(symbol, direction, quantity, position_id)


def test_both_flat_are_safe_for_new_entry():
    decision = new_entry_allowed(None, [])
    assert decision.action == ALLOW
    assert decision.safe


def test_broker_position_without_local_state_halts():
    decision = reconcile_position(None, [broker()])
    assert decision.action == HALT
    assert not decision.safe


def test_local_position_without_broker_state_halts():
    decision = reconcile_position(local(), [])
    assert decision.action == HALT
    assert not decision.safe


def test_matching_position_state_reconciles():
    decision = reconcile_position(local(), [broker()])
    assert decision.action == ALLOW
    assert decision.safe


def test_direction_mismatch_halts():
    decision = reconcile_position(local(LONG), [broker(direction="SHORT")])
    assert not decision.safe


def test_quantity_mismatch_halts():
    decision = reconcile_position(local(quantity=1.0), [broker(quantity=1.1)])
    assert not decision.safe


def test_multiple_broker_positions_halts():
    decision = reconcile_position(local(), [broker("LONG", 1.0, "p1"), broker("LONG", 1.0, "p2")])
    assert not decision.safe


def test_duplicate_broker_id_halts():
    decision = reconcile_position(local(), [broker("LONG", 1.0, "p1"), broker("SHORT", 1.0, "p1")])
    assert not decision.safe


def test_new_entry_is_blocked_when_existing_position_matches():
    decision = new_entry_allowed(local(), [broker()])
    assert decision.action == HALT
    assert not decision.safe


def test_invalid_quantity_tolerance_is_rejected():
    with pytest.raises(ValueError):
        reconcile_position(None, [], quantity_tolerance=-1)
