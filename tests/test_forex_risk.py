import pytest

from strategy.forex_risk import (
    ForexRiskLimits,
    ForexSymbolContract,
    calculate_forex_lot_size,
    check_currency_exposure,
    evaluate_forex_risk,
    extract_currencies,
)


@pytest.fixture
def eurusd_contract():
    return ForexSymbolContract(
        symbol="EURUSD",
        digits=5,
        point=0.00001,
        trade_tick_value=1.0,
        trade_tick_size=0.00001,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
    )


@pytest.fixture
def usdjpy_contract():
    return ForexSymbolContract(
        symbol="USDJPY",
        digits=3,
        point=0.001,
        trade_tick_value=0.67,
        trade_tick_size=0.001,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
    )


def test_extract_currencies():
    assert extract_currencies("EURUSD") == ("EUR", "USD")
    assert extract_currencies("GBP_JPY_m") == ("GBP", "JPY")
    assert extract_currencies("XAUUSD.raw") == ("XAU", "USD")


def test_currency_exposure_check():
    active = ["EURUSD", "GBPUSD"]
    allowed, reason = check_currency_exposure("USDJPY", active, max_per_currency=2)
    assert not allowed
    assert "currency concentration limit reached for USD" in reason

    allowed, reason = check_currency_exposure("EURGBP", active, max_per_currency=2)
    assert allowed


def test_eurusd_lot_sizing(eurusd_contract):
    lots = calculate_forex_lot_size(
        equity=10000.0,
        entry=1.10000,
        stop=1.09800,
        contract=eurusd_contract,
        risk_fraction=0.01,
    )
    assert pytest.approx(lots) == 0.50


def test_lot_size_flooring(eurusd_contract):
    lots = calculate_forex_lot_size(
        equity=10000.0,
        entry=1.10000,
        stop=1.09770,
        contract=eurusd_contract,
        risk_fraction=0.01,
    )
    assert pytest.approx(lots) == 0.43
    assert (230 * 1.0 * lots) <= 100.0


def test_evaluate_forex_risk_full_pass(eurusd_contract):
    limits = ForexRiskLimits(risk_per_trade_fraction=0.01, max_open_positions=3)
    dec = evaluate_forex_risk(
        equity=5000.0,
        entry=1.10000,
        stop=1.09800,
        contract=eurusd_contract,
        limits=limits,
        daily_realized_loss=0.0,
        active_symbols=[],
    )
    assert dec.allowed
    assert dec.lot_size == pytest.approx(0.25)
    assert dec.sl_pips == pytest.approx(20.0)


def test_evaluate_forex_risk_rejects_duplicate_symbol(eurusd_contract):
    limits = ForexRiskLimits(max_open_positions=3)
    dec = evaluate_forex_risk(
        equity=10000.0,
        entry=1.10000,
        stop=1.09800,
        contract=eurusd_contract,
        limits=limits,
        active_symbols=["EURUSD"],
    )
    assert not dec.allowed
    assert dec.reason == "position already open for EURUSD"


def test_evaluate_forex_risk_daily_loss_limit(eurusd_contract):
    limits = ForexRiskLimits(max_daily_loss_fraction=0.03)
    dec = evaluate_forex_risk(
        equity=10000.0,
        entry=1.10000,
        stop=1.09800,
        contract=eurusd_contract,
        limits=limits,
        daily_realized_loss=350.0,
    )
    assert not dec.allowed
    assert "daily loss limit reached" in dec.reason
