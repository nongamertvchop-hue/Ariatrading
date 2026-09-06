from strategy.candles import Candle
from strategy.levels_v2 import PriceZone, SUPPORT, RESISTANCE
from strategy.signals_v2 import LONG, SHORT, WAIT, evaluate_long, evaluate_short


def test_long_waits_for_support_test():
    support = PriceZone(99.5, 100.5, SUPPORT, 3)
    candle = Candle(102, 103, 101.5, 102.5)
    assert evaluate_long(candle, support).action == WAIT


def test_long_requires_bullish_confirmation_after_support_test():
    support = PriceZone(99.5, 100.5, SUPPORT, 3)
    confirmed = Candle(100.2, 102.0, 99.8, 101.8)
    weak = Candle(100.2, 101.0, 99.8, 100.0)
    assert evaluate_long(confirmed, support).action == LONG
    assert evaluate_long(weak, support).action == WAIT


def test_long_waits_when_support_breaks():
    support = PriceZone(99.5, 100.5, SUPPORT, 3)
    broken = Candle(100.0, 100.2, 98.5, 99.0)
    assert evaluate_long(broken, support).action == WAIT


def test_short_requires_bearish_confirmation_after_resistance_test():
    resistance = PriceZone(109.5, 110.5, RESISTANCE, 3)
    confirmed = Candle(109.8, 110.2, 108.0, 108.2)
    weak = Candle(109.0, 110.2, 108.8, 109.8)
    assert evaluate_short(confirmed, resistance).action == SHORT
    assert evaluate_short(weak, resistance).action == WAIT


def test_short_waits_when_resistance_breaks():
    resistance = PriceZone(109.5, 110.5, RESISTANCE, 3)
    broken = Candle(110.0, 111.5, 109.9, 111.0)
    assert evaluate_short(broken, resistance).action == WAIT
