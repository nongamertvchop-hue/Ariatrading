from strategy.candles import Candle
from strategy.levels_v2 import PriceZone, SUPPORT, RESISTANCE
from strategy.protection import Protection, long_entry_allowed, short_entry_allowed, resistance_state, support_state


def test_support_inside_zone_is_safe():
    support = PriceZone(99.5, 100.5, SUPPORT, 3)
    candle = Candle(100.4, 101.5, 99.7, 101.2)
    assert support_state(candle, support, 0.3) == Protection.SAFE
    assert long_entry_allowed(candle, support, 0.3)


def test_support_wick_penetration_is_danger_not_entry():
    support = PriceZone(99.5, 100.5, SUPPORT, 3)
    candle = Candle(100.2, 101.0, 99.3, 100.7)
    assert support_state(candle, support, 0.3) == Protection.DANGER
    assert not long_entry_allowed(candle, support, 0.3)


def test_support_deep_break_is_broken():
    support = PriceZone(99.5, 100.5, SUPPORT, 3)
    candle = Candle(100.0, 100.2, 98.5, 99.0)
    assert support_state(candle, support, 0.3) == Protection.BROKEN
    assert not long_entry_allowed(candle, support, 0.3)


def test_resistance_inside_zone_is_safe():
    resistance = PriceZone(109.5, 110.5, RESISTANCE, 3)
    candle = Candle(109.8, 110.3, 108.0, 108.4)
    assert resistance_state(candle, resistance, 0.3) == Protection.SAFE
    assert short_entry_allowed(candle, resistance, 0.3)


def test_resistance_wick_penetration_is_danger_not_entry():
    resistance = PriceZone(109.5, 110.5, RESISTANCE, 3)
    candle = Candle(109.8, 110.8, 108.8, 109.0)
    assert resistance_state(candle, resistance, 0.3) == Protection.DANGER
    assert not short_entry_allowed(candle, resistance, 0.3)


def test_resistance_deep_break_is_broken():
    resistance = PriceZone(109.5, 110.5, RESISTANCE, 3)
    candle = Candle(110.0, 111.5, 109.9, 111.0)
    assert resistance_state(candle, resistance, 0.3) == Protection.BROKEN
    assert not short_entry_allowed(candle, resistance, 0.3)
