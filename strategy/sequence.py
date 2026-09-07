"""Multi-candle price-action sequence for the two basic setups.

Sequence:
    APPROACH -> TEST -> (FAKE BREAK + RECLAIM or CLEAN REJECTION) -> CONFIRM -> SIGNAL

The dedicated fake-breakout classifier is used here, so breakout state and
sequence state cannot silently disagree. Confirmation requires the new candle
to close back beyond the zone with directional pressure; it does not require
breaking the reaction candle's extreme because the core idea is a level hold,
not a momentum-breakout strategy.

Educational/demo only. No orders are placed here.
"""

from dataclasses import dataclass

from .candles import Candle, candle_pressure, rejection_pressure
from .fake_breakout import (
    FAKE_BREAKOUT,
    NO_BREAKOUT,
    TRUE_BREAKOUT,
    WAIT as BREAKOUT_WAIT,
    classify_resistance_breakout,
    classify_support_breakout,
)
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
    breakout_state: str = NO_BREAKOUT


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
    """Evaluate a completed test/reaction followed by confirmation."""
    get_timeframe_config(timeframe)
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

    buffer = adaptive_confirmation_buffer(candles[:-1], timeframe)
    current_index = len(candles) - 1
    current = _candle(candles[current_index])
    start = max(0, current_index - max_test_age)

    for test_index in range(current_index - 1, start - 1, -1):
        test = _candle(candles[test_index])
        if not _touches(test, zone):
            continue

        if direction == LONG:
            breakout = classify_support_breakout(test, zone, buffer)
            if breakout.state in {TRUE_BREAKOUT, BREAKOUT_WAIT}:
                if breakout.state == TRUE_BREAKOUT:
                    return SequenceResult(WAIT, BROKEN, "support closed decisively below the zone", test_index, current_index, breakout_state=breakout.state)
                continue
            # A classified fake breakout is itself the reclaim setup. The
            # confirmation candle is the second independent filter.
            reclaim = breakout.state == FAKE_BREAKOUT
            rejection = (
                breakout.state == NO_BREAKOUT
                and test.close > zone.high
                and rejection_pressure(test, LONG)
            )
            if not (reclaim or rejection):
                continue
            if candle_pressure(current) != "BUYING":
                return SequenceResult(WAIT, CONFIRM, "support reacted but confirmation candle is not strongly bullish", test_index, current_index, breakout_state=breakout.state)
            if current.close <= zone.high:
                return SequenceResult(WAIT, CONFIRM, "buyers have not confirmed a close above support", test_index, current_index, breakout_state=breakout.state)
            return SequenceResult(LONG, CONFIRM, "support test followed by bullish confirmation", test_index, current_index, current.close, breakout.state)

        breakout = classify_resistance_breakout(test, zone, buffer)
        if breakout.state in {TRUE_BREAKOUT, BREAKOUT_WAIT}:
            if breakout.state == TRUE_BREAKOUT:
                return SequenceResult(WAIT, BROKEN, "resistance closed decisively above the zone", test_index, current_index, breakout_state=breakout.state)
            continue
        # Mirror the support rule: a fake breakout supplies the reclaim setup;
        # the following completed candle must still confirm directionally.
        reclaim = breakout.state == FAKE_BREAKOUT
        rejection = (
            breakout.state == NO_BREAKOUT
            and test.close < zone.low
            and rejection_pressure(test, SHORT)
        )
        if not (reclaim or rejection):
            continue
        if candle_pressure(current) != "SELLING":
            return SequenceResult(WAIT, CONFIRM, "resistance reacted but confirmation candle is not strongly bearish", test_index, current_index, breakout_state=breakout.state)
        if current.close >= zone.low:
            return SequenceResult(WAIT, CONFIRM, "sellers have not confirmed a close below resistance", test_index, current_index, breakout_state=breakout.state)
        return SequenceResult(SHORT, CONFIRM, "resistance test followed by bearish confirmation", test_index, current_index, current.close, breakout.state)

    return SequenceResult(WAIT, APPROACH, "no complete test-and-confirmation sequence")
