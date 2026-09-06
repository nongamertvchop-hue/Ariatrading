from strategy.market_structure import BEARISH, BULLISH, UNKNOWN, analyze_market_structure


def test_bullish_structure_from_confirmed_swings():
    candles = [
        {"open": 1.0, "high": 1.20, "low": 0.98, "close": 1.10},
        {"open": 1.10, "high": 1.30, "low": 1.05, "close": 1.25},
        {"open": 1.25, "high": 1.26, "low": 1.00, "close": 1.08},
        {"open": 1.08, "high": 1.35, "low": 1.02, "close": 1.30},
        {"open": 1.30, "high": 1.31, "low": 1.10, "close": 1.15},
        {"open": 1.15, "high": 1.40, "low": 1.08, "close": 1.35},
        {"open": 1.35, "high": 1.36, "low": 1.20, "close": 1.28},
    ]
    result = analyze_market_structure(candles, strength=1)
    assert result.bias == BULLISH


def test_bearish_structure_from_confirmed_swings():
    candles = [
        {"open": 1.15, "high": 1.20, "low": 1.10, "close": 1.18},
        {"open": 1.18, "high": 1.30, "low": 1.05, "close": 1.10},
        {"open": 1.10, "high": 1.25, "low": 1.00, "close": 1.08},
        {"open": 1.08, "high": 1.20, "low": 1.02, "close": 1.10},
        {"open": 1.10, "high": 1.15, "low": 0.90, "close": 0.98},
        {"open": 0.98, "high": 1.10, "low": 0.92, "close": 0.95},
        {"open": 0.95, "high": 1.05, "low": 0.88, "close": 0.92},
    ]
    result = analyze_market_structure(candles, strength=1)
    assert result.bias == BEARISH


def test_empty_structure_is_unknown():
    assert analyze_market_structure([]).bias == UNKNOWN
