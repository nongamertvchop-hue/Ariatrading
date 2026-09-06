from strategy.candles import Candle
from strategy.fake_breakout import (
    FAKE_BREAKOUT,
    NO_BREAKOUT,
    TRUE_BREAKOUT,
    WAIT,
    classify_resistance_breakout,
    classify_support_breakout,
    long_protection,
    short_protection,
)
from strategy.levels_v2 import PriceZone, RESISTANCE, SUPPORT


def test_support_wick_below_but_close_above_is_fake_breakout():
    zone = PriceZone(99.5, 100.5, SUPPORT, 3)
    candle = Candle(100.2, 101.0, 99.2, 100.2)
    result = classify_support_breakout(candle, zone, 0.2)
    assert result.state == FAKE_BREAKOUT
    assert long_protection(candle, zone, 0.2) == WAIT


def test_support_clear_close_below_is_true_breakout():
    zone = PriceZone(99.5, 100.5, SUPPORT, 3)
    candle = Candle(100.0, 100.2, 98.8, 99.1)
    result = classify_support_breakout(candle, zone, 0.2)
    assert result.state == TRUE_BREAKOUT
    assert long_protection(candle, zone, 0.2) == WAIT


def test_support_without_break_is_no_breakout():
    zone = PriceZone(99.5, 100.5, SUPPORT, 3)
    candle = Candle(101.0, 102.0, 100.0, 101.5)
    assert classify_support_breakout(candle, zone).state == NO_BREAKOUT


def test_resistance_wick_above_but_close_below_is_fake_breakout():
    zone = PriceZone(109.5, 110.5, RESISTANCE, 3)
    candle = Candle(109.8, 110.8, 108.8, 109.8)
    result = classify_resistance_breakout(candle, zone, 0.2)
    assert result.state == FAKE_BREAKOUT
    assert short_protection(candle, zone, 0.2) == WAIT


def test_resistance_clear_close_above_is_true_breakout():
    zone = PriceZone(109.5, 110.5, RESISTANCE, 3)
    candle = Candle(110.0, 111.2, 109.8, 110.9)
    result = classify_resistance_breakout(candle, zone, 0.2)
    assert result.state == TRUE_BREAKOUT
    assert short_protection(candle, zone, 0.2) == WAIT


def test_resistance_without_break_is_no_breakout():
    zone = PriceZone(109.5, 110.5, RESISTANCE, 3)
    candle = Candle(108.8, 110.0, 108.0, 109.2)
    assert classify_resistance_breakout(candle, zone).state == NO_BREAKOUT
