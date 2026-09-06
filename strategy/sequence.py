"""Multi-candle price-action sequence for the two basic setups.

Sequence:
    APPROACH -> TEST -> (FAKE BREAK + RECLAIM or CLEAN REJECTION) -> CONFIRM -> SIGNAL

Only completed candles at or before the evaluation point are used. This module
is educational/demo code and never places orders.
"""

from dataclasses import dataclass

from .candles import Candle, candle_pressure
from .levels_v2 import PriceZone, SUPPORT, RESISTANCE
from .timeframe import adaptive_confirmation_buffer, get_timeframe_config

LONG = "LONG"
SHORT = "SHORT"
WAIT = "WAIT"

APPROACH = "APPROACH"
TEST = "TEST"
RECLAIM = "RECLAIM"
REJECT = "REJECT"
CONFIRM = "CONFIRM"
BROKEN = "BROKEN"


@dataclass(frozen=True)
class SequenceResult:
    action: str
    state: str
    reason: str
    test_index: int | None = None
    confirmation_index: int | None = None
    entry_reference: float | None = None


def _candle(raw: dict) -> Candle:
    return Candle(float(raw["open"]), float(raw["high"]), float(raw["low"]), float(raw["close"]))


def _touches(candle: Candle, zone: PriceZone) -> bool:
    return candle.low <= zone.high and candle.high >= zone.low


def evaluate_sequence(
    candles: list[dict],
    zone: PriceZone,
    timeframe: str,
    direction: str,
    max_test_age: int = 3,
) -> SequenceResult:
    """Evaluate a completed sequence ending at the latest candle.

    A signal needs at least two completed candles: one test/reclaim/rejection
    candle followed by a separate confirmation candle. A break that closes
    beyond the zone is treated as invalid for the reversal setup.
    """
    config = get_timeframe_config(timeframe)
    if direction not in {LONG, SHORT}:
        raise ValueError("direction must be LONG or SHORT")
    if direction == LONG and zone.kind != SUPPORT:
        raise ValueError("LONG requires SUPPORT")
    if direction == SHORT and zone.kind != RESISTANCE:
        raise ValueError("SHORT requires RESISTANCE")
    if max_test_age < 1:
        raise ValueError("max_test_age must be >= 1")
    if len(candles) < 2:
        return SequenceResult(WAIT, APPROACH, "not enough completed candles")

    buffer = adaptive_confirmation_buffer(candles[:-1], timeframe) if len(candles) > 1 else 0.0
    current_index = len(candles) - 1
    current = _candle(candles[current_index])
    start = max(0, current_index - max_test_age)

    for test_index in range(current_index - 1, start - 1, -1):
        test = _candle(candles[test_index])
        if not _touches(test, zone):
            continue

        if direction == LONG:
            if test.close < zone.low - buffer:
                return SequenceResult(WAIT, BROKEN, "support closed decisively below the zone", test_index, current_index)
            reclaim = test.low < zone.low and test.close >= zone.low
            rejection = test.close > zone.high and candle_pressure(test) == "BUYING"
            if not (reclaim or rejection):
                continue
            if candle_pressure(current) != "BUYING":
                return SequenceResult(WAIT, CONFIRM, "support reacted but confirmation candle is not strongly bullish", test_index, current_index)
            if current.close <= test.high or current.close <= zone.high:
                return SequenceResult(WAIT, CONFIRM, "buyers have not confirmed a break above the test candle", test_index, current_index)
            state = RECLAIM if reclaim else REJECT
            return SequenceResult(LONG, CONFIRM, "support test followed by bullish confirmation", test_index, current_index, current.close)

        if test.close > zone.high + buffer:
            return SequenceResult(WAIT, BROKEN, "resistance closed decisively above the zone", test_index, current_index)
        reclaim = test.high > zone.high and test.close <= zone.high
        rejection = test.close < zone.low and candle_pressure(test) == "SELLING"
        if not (reclaim or rejection):
            continue
        if candle_pressure(current) != "SELLING":
            return SequenceResult(WAIT, CONFIRM, "resistance reacted but confirmation candle is not strongly bearish", test_index, current_index)
        if current.close >= test.low or current.close >= zone.low:
            return SequenceResult(WAIT, CONFIRM, "sellers have not confirmed a break below the test candle", test_index, current_index)
        state = RECLAIM if reclaim else REJECT
        return SequenceResult(SHORT, CONFIRM, "resistance test followed by bearish confirmation", test_index, current_index, current.close)

    return SequenceResult(WAIT, APPROACH, "no complete test-and-confirmation sequence")
