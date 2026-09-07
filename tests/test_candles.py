import math

import pytest

from strategy.candles import Candle, candle_pressure, rejection_pressure


@pytest.mark.parametrize(
    "field",
    ["open", "high", "low", "close"],
)
def test_non_finite_ohlc_is_rejected(field):
    values = {"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0}
    values[field] = math.nan

    with pytest.raises(ValueError, match="finite"):
        Candle(**values)


@pytest.mark.parametrize(
    "field",
    ["open", "high", "low", "close"],
)
def test_infinite_ohlc_is_rejected(field):
    values = {"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0}
    values[field] = math.inf

    with pytest.raises(ValueError, match="finite"):
        Candle(**values)


def test_zero_range_candle_has_neutral_pressure():
    candle = Candle(1.0, 1.0, 1.0, 1.0)

    assert candle.range == 0.0
    assert candle.close_position == 0.5
    assert candle_pressure(candle) == "NEUTRAL"


def test_rejection_pressure_rejects_unknown_direction():
    candle = Candle(1.0, 1.1, 0.9, 1.05)

    with pytest.raises(ValueError, match="direction"):
        rejection_pressure(candle, "SIDEWAYS")
