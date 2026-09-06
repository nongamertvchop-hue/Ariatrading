from strategy.candles import Candle, candle_pressure
from strategy.levels import PriceLevel, cluster_levels, find_swing_highs, find_swing_lows
from strategy.signals import LONG, SHORT, WAIT, check_long_setup, check_short_setup


def test_example_candle_is_selling_pressure():
    candle = Candle(open=100, high=102, low=90, close=91)
    assert candle_pressure(candle) == "SELLING"
    assert candle.close_position == 1 / 12


def test_bullish_candle_near_high_is_buying_pressure():
    candle = Candle(open=100, high=110, low=99, close=109)
    assert candle_pressure(candle) == "BUYING"


def test_cluster_levels_counts_touches():
    clusters = cluster_levels([1.0000, 1.0004, 1.0100], tolerance=0.001)
    assert clusters[0][1] == 2
    assert clusters[1][1] == 1


def test_swing_detection():
    candles = [
        {"high": 10, "low": 8},
        {"high": 9, "low": 6},
        {"high": 11, "low": 7},
        {"high": 8, "low": 5},
        {"high": 10, "low": 7},
        {"high": 9, "low": 6},
    ]
    assert find_swing_lows(candles, strength=1) == [6, 5]
    assert find_swing_highs(candles, strength=1) == [11, 10]


def test_long_requires_support_test_and_buying_confirmation():
    support = PriceLevel(100.0, "SUPPORT", 2)
    bullish = Candle(open=100.2, high=102.0, low=99.8, close=101.7)
    bearish = Candle(open=101.0, high=101.2, low=99.7, close=100.0)
    assert check_long_setup(bullish, support, 0.5) == LONG
    assert check_long_setup(bearish, support, 0.5) == WAIT


def test_short_requires_resistance_test_and_selling_confirmation():
    resistance = PriceLevel(110.0, "RESISTANCE", 2)
    bearish = Candle(open=109.8, high=110.2, low=108.0, close=108.2)
    bullish = Candle(open=108.5, high=110.1, low=108.2, close=109.9)
    assert check_short_setup(bearish, resistance, 0.5) == SHORT
    assert check_short_setup(bullish, resistance, 0.5) == WAIT
