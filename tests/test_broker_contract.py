import pytest

from strategy.broker_contract import SymbolContract, validate_order_contract


@pytest.fixture
def contract() -> SymbolContract:
    return SymbolContract(
        symbol="EURUSD",
        digits=5,
        point=0.00001,
        volume_min=0.01,
        volume_max=5.0,
        volume_step=0.01,
    )


def test_valid_symbol_contract_accepts_normal_order(contract):
    result = validate_order_contract(
        contract,
        symbol="EURUSD",
        price=1.12345,
        quantity=0.10,
    )
    assert result.allowed


def test_wrong_symbol_is_rejected(contract):
    result = validate_order_contract(
        contract,
        symbol="GBPUSD",
        price=1.12345,
        quantity=0.10,
    )
    assert not result.allowed
    assert "symbol" in result.reason


@pytest.mark.parametrize("quantity", [0.0, 0.001, 5.01])
def test_volume_bounds_are_hard(contract, quantity):
    result = validate_order_contract(
        contract,
        symbol="EURUSD",
        price=1.12345,
        quantity=quantity,
    )
    assert not result.allowed


def test_volume_step_is_enforced(contract):
    result = validate_order_contract(
        contract,
        symbol="EURUSD",
        price=1.12345,
        quantity=0.015,
    )
    assert not result.allowed
    assert "step" in result.reason


def test_price_precision_is_enforced(contract):
    result = validate_order_contract(
        contract,
        symbol="EURUSD",
        price=1.123456,
        quantity=0.10,
    )
    assert not result.allowed
    assert "precision" in result.reason


def test_invalid_contract_invariants_are_rejected():
    with pytest.raises(ValueError):
        SymbolContract("EURUSD", 5, 0.00001, 0.10, 0.01, 0.01)

    with pytest.raises(ValueError):
        SymbolContract("EURUSD", 5, 0.00001, 0.01, 1.0, 0.0)
