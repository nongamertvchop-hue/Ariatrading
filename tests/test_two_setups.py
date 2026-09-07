from strategy.candles import Candle
from strategy.engine import LONG, SHORT, WAIT
from strategy.levels_v2 import PriceZone, RESISTANCE, SUPPORT
from strategy.two_setups import _active_zones, evaluate_two_setups


def _c(open_, high, low, close):
    return {"open": open_, "high": high, "low": low, "close": close}


def test_recently_broken_support_is_not_active():
    zone = PriceZone(1.0990, 1.1000, SUPPORT, 3)
    candles = [
        _c(1.1010, 1.1015, 1.0995, 1.1008),
        _c(1.1008, 1.1009, 1.0980, 1.0975),
    ]

    active = _active_zones([zone], candles, "15m")

    assert active == []


def test_zone_can_be_relevant_again_after_later_interaction():
    zone = PriceZone(1.0990, 1.1000, SUPPORT, 3)
    candles = [
        _c(1.1010, 1.1015, 1.0995, 1.1008),
        _c(1.1008, 1.1009, 1.0980, 1.0975),
        _c(1.0975, 1.1002, 1.0970, 1.0998),
    ]

    active = _active_zones([zone], candles, "15m")

    assert active == [zone]


def test_long_setup_is_detected_from_confirmed_repeated_support():
    candles = [
        _c(1.1020, 1.1022, 1.1018, 1.1020),
        _c(1.1020, 1.1022, 1.1008, 1.1010),
        _c(1.1010, 1.1012, 1.1000, 1.1002),
        _c(1.1002, 1.1015, 1.1001, 1.1013),
        _c(1.1013, 1.1020, 1.1011, 1.1018),
        _c(1.1018, 1.1020, 1.1010, 1.1012),
        _c(1.1012, 1.1018, 1.1007, 1.1015),
        _c(1.1015, 1.1017, 1.1001, 1.1003),
        _c(1.1003, 1.1015, 1.1002, 1.1012),
        _c(1.1012, 1.1020, 1.1010, 1.1018),
        _c(1.1018, 1.1020, 1.1008, 1.1010),
        _c(1.0998, 1.10065, 1.0996, 1.1006),
        _c(1.1006, 1.1017, 1.1004, 1.1015),
    ]

    result = evaluate_two_setups(candles, "15m")

    assert result.signal.action == LONG
    assert result.signal.confirmation_index == len(candles) - 1
    assert result.signal.test_index < result.signal.confirmation_index
    assert result.signal.test_index >= 0
    assert result.signal.stop_reference is not None
    assert result.signal.stop_reference < result.signal.zone.low
    assert result.support_zones


def test_short_setup_exposes_protective_stop_above_resistance():
    candles = [
        _c(1.1080, 1.1085, 1.1075, 1.1082),
        _c(1.1082, 1.1095, 1.1080, 1.1092),
        _c(1.1092, 1.1110, 1.1090, 1.1094),
        _c(1.1094, 1.1100, 1.1078, 1.1082),
        _c(1.1082, 1.1096, 1.1075, 1.1088),
        _c(1.1088, 1.1108, 1.1085, 1.1096),
        _c(1.1096, 1.1100, 1.1079, 1.1084),
        _c(1.1084, 1.1097, 1.1070, 1.1089),
        _c(1.1089, 1.1112, 1.1086, 1.1098),
        _c(1.1098, 1.1100, 1.1070, 1.1080),
        _c(1.1080, 1.1097, 1.1072, 1.1086),
        _c(1.1090, 1.1110, 1.1086, 1.1100),
        _c(1.1100, 1.1103, 1.1068, 1.1070),
    ]

    result = evaluate_two_setups(candles, "15m")

    assert result.signal.action == SHORT
    assert result.signal.stop_reference is not None
    assert result.signal.zone is not None
    assert result.signal.stop_reference > result.signal.zone.high


def test_latest_candle_is_not_used_to_construct_zones():
    candles = [
        _c(1.1020, 1.1022, 1.1018, 1.1020),
        _c(1.1020, 1.1022, 1.1008, 1.1010),
        _c(1.1010, 1.1012, 1.1000, 1.1002),
        _c(1.1002, 1.1015, 1.1001, 1.1013),
        _c(1.1013, 1.1020, 1.1011, 1.1018),
        _c(1.1018, 1.1020, 1.1010, 1.1012),
        _c(1.1012, 1.1018, 1.1007, 1.1015),
        _c(1.1015, 1.1017, 1.1001, 1.1003),
        _c(1.1003, 1.1015, 1.1002, 1.1012),
        _c(1.1012, 1.1020, 1.1010, 1.1018),
        _c(1.1018, 1.1020, 1.1008, 1.1010),
        _c(1.1009, 1.1011, 1.1007, 1.1008),
        _c(1.0990, 1.1050, 1.0980, 1.1000),
    ]

    result = evaluate_two_setups(candles, "15m")

    # The extreme high/low on the latest candle cannot manufacture a new zone.
    assert all(zone.high < 1.1050 for zone in result.resistance_zones)
    assert all(zone.low > 1.0980 for zone in result.support_zones)


def test_two_setups_wait_when_history_is_too_short():
    candles = [_c(1.0, 1.01, 0.99, 1.0)] * 7

    result = evaluate_two_setups(candles, "15m")

    assert result.signal.action == WAIT
    assert result.support_zones == ()
    assert result.resistance_zones == ()
