from __future__ import annotations

import math

import pytest

from interop.python.adapter import validate_candle, validate_sequence


VALID = {"time": 1, "open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15}


def test_valid_candle_is_canonical() -> None:
    candle = validate_candle(VALID)
    assert candle.time == 1
    assert candle.high >= max(candle.open, candle.close)
    assert candle.low <= min(candle.open, candle.close)


@pytest.mark.parametrize(
    "bad",
    [
        {**VALID, "high": 1.14},
        {**VALID, "low": 1.16},
        {**VALID, "close": math.nan},
        {**VALID, "open": 0},
    ],
)
def test_invalid_geometry_or_nonfinite_prices_fail_closed(bad: dict) -> None:
    with pytest.raises(ValueError):
        validate_candle(bad)


def test_sequence_requires_strictly_increasing_time() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        validate_sequence([VALID, {**VALID, "time": 1}])
