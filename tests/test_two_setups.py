from strategy.two_setups import evaluate_two_setups
from strategy.engine import LONG, WAIT


def _c(open_, high, low, close):
    return {"open": open_, "high": high, "low": low, "close": close}


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
    assert result.support_zones


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
