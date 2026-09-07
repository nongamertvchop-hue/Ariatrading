import pytest

from strategy.broker_contract import SymbolContract
from strategy.position_reconciliation import (
    ALLOW,
    HALT,
    LONG,
    LocalPositionState,
    PositionSnapshot,
    new_entry_allowed,
    reconcile_position,
)


def broker(direction=LONG, quantity=1.0, position_id="p1", symbol="EURUSD", average_entry_price=None):
    return PositionSnapshot(symbol, direction, quantity, position_id, average_entry_price)


def local(direction=LONG, quantity=1.0, position_id="p1", symbol="EURUSD", average_entry_price=None):
    return LocalPositionState(symbol, direction, quantity, position_id, average_entry_price)


def contract():
    return SymbolContract(
        symbol="EURUSD",
        digits=5,
        point=0.00001,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
    )


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
    assert not decision.safe


def test_matching_position_state_reconciles():
    decision = reconcile_position(local(), [broker()])
    assert decision.action == ALLOW
    assert decision.safe


def test_average_entry_price_mismatch_halts():
    decision = reconcile_position(
        local(average_entry_price=1.10000),
        [broker(average_entry_price=1.10020)],
        price_tolerance=0.00001,
    )
    assert decision.action == HALT
    assert "average entry price" in decision.reason


def test_missing_broker_average_entry_price_halts_when_local_has_one():
    decision = reconcile_position(
        local(average_entry_price=1.10000),
        [broker()],
    )
    assert not decision.safe


def test_average_entry_price_within_tolerance_reconciles():
    decision = reconcile_position(
        local(average_entry_price=1.10000),
        [broker(average_entry_price=1.10001)],
        price_tolerance=0.00001,
    )
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


def test_broker_contract_symbol_mismatch_halts():
    decision = reconcile_position(
        local(symbol="GBPUSD", average_entry_price=1.30000),
        [broker(symbol="GBPUSD", average_entry_price=1.30000)],
        broker_contract=contract(),
    )
    assert not decision.safe
    assert "broker position symbol" in decision.reason


def test_broker_contract_price_precision_mismatch_halts():
    decision = reconcile_position(
        local(average_entry_price=1.10000),
        [broker(average_entry_price=1.100001)],
        broker_contract=contract(),
    )
    assert not decision.safe
    assert "symbol contract" in decision.reason


def test_broker_contract_volume_step_mismatch_halts_even_without_entry_price():
    decision = reconcile_position(
        local(quantity=0.015),
        [broker(quantity=0.015)],
        broker_contract=contract(),
    )
    assert not decision.safe
    assert "volume step" in decision.reason


def test_matching_position_contract_reconciles():
    decision = reconcile_position(
        local(quantity=1.25, average_entry_price=1.10000),
        [broker(quantity=1.25, average_entry_price=1.10000)],
        broker_contract=contract(),
    )
    assert decision.action == ALLOW
    assert decision.safe


def test_new_entry_is_blocked_when_existing_position_matches():
    decision = new_entry_allowed(local(), [broker()])
    assert decision.action == HALT
    assert not decision.safe


def test_invalid_quantity_tolerance_is_rejected():
    with pytest.raises(ValueError):
        reconcile_position(None, [], quantity_tolerance=-1)


def test_invalid_price_tolerance_is_rejected():
    with pytest.raises(ValueError):
        reconcile_position(None, [], price_tolerance=-1)


def test_invalid_average_entry_price_is_rejected():
    with pytest.raises(ValueError):
        broker(average_entry_price=0)
