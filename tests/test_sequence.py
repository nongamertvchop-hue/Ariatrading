from strategy.levels_v2 import PriceZone, RESISTANCE, SUPPORT
from strategy.sequence import LONG, SHORT, WAIT, CONFIRM, RECLAIM, evaluate_sequence


def test_support_rejection_then_confirmation_long():
    zone = PriceZone(1.0990, 1.1000, SUPPORT, 3)
    candles = [
        {"open": 1.1010, "high": 1.1015, "low": 1.0995, "close": 1.0998},
        {"open": 1.0997, "high": 1.1015, "low": 1.0992, "close": 1.1008},
        {"open": 1.1008, "high": 1.1025, "low": 1.1005, "close": 1.1022},
    ]
    result = evaluate_sequence(candles, zone, "15m", LONG)
    assert result.action == LONG
    assert result.state == CONFIRM
    assert result.confirmation_index == 2


def test_support_fake_break_reclaim_then_long():
    zone = PriceZone(1.0990, 1.1000, SUPPORT, 3)
    candles = [
        {"open": 1.1010, "high": 1.1012, "low": 1.0985, "close": 1.0995},
        {"open": 1.0995, "high": 1.1015, "low": 1.0993, "close": 1.1012},
    ]
    result = evaluate_sequence(candles, zone, "15m", LONG)
    assert result.action == LONG
    assert result.state == CONFIRM
    assert result.test_index == 0


def test_true_support_break_is_wait():
    zone = PriceZone(1.0990, 1.1000, SUPPORT, 3)
    candles = [
        {"open": 1.1000, "high": 1.1005, "low": 1.0975, "close": 1.0980},
        {"open": 1.0980, "high": 1.0985, "low": 1.0965, "close": 1.0970},
    ]
    result = evaluate_sequence(candles, zone, "15m", LONG)
    assert result.action == WAIT


def test_resistance_rejection_then_confirmation_short():
    zone = PriceZone(1.1090, 1.1100, RESISTANCE, 3)
    candles = [
        {"open": 1.1080, "high": 1.1105, "low": 1.1075, "close": 1.1092},
        {"open": 1.1092, "high": 1.1095, "low": 1.1070, "close": 1.1080},
        {"open": 1.1080, "high": 1.1085, "low": 1.1050, "close": 1.1055},
    ]
    result = evaluate_sequence(candles, zone, "15m", SHORT)
    assert result.action == SHORT
    assert result.state == CONFIRM
    assert result.confirmation_index == 2


def test_resistance_fake_break_reclaim_then_short():
    zone = PriceZone(1.1090, 1.1100, RESISTANCE, 3)
    candles = [
        {"open": 1.1095, "high": 1.1115, "low": 1.1090, "close": 1.1096},
        {"open": 1.1096, "high": 1.1097, "low": 1.1075, "close": 1.1080},
    ]
    result = evaluate_sequence(candles, zone, "15m", SHORT)
    assert result.action == SHORT
    assert result.state == CONFIRM
    assert result.test_index == 0


def test_ambiguous_test_returns_wait():
    zone = PriceZone(1.0990, 1.1000, SUPPORT, 3)
    candles = [
        {"open": 1.1000, "high": 1.1005, "low": 1.0992, "close": 1.0996},
        {"open": 1.0996, "high": 1.1002, "low": 1.0994, "close": 1.0998},
    ]
    result = evaluate_sequence(candles, zone, "15m", LONG)
    assert result.action == WAIT
