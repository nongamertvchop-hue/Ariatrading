"""Causal outcome labeling for previously emitted paper signals.

This module is research-only. It never changes a signal and never executes an
order. Outcomes are assigned only from candles strictly after the signal bar.

When stop and target are both touched by the same OHLC candle, the intrabar
path is unknowable from OHLC alone, so the result is explicitly AMBIGUOUS
rather than assuming a favorable or unfavorable path.
"""

from dataclasses import dataclass
from math import isfinite
from typing import Literal

LONG = "LONG"
SHORT = "SHORT"
WAIT = "WAIT"
WIN = "WIN"
LOSS = "LOSS"
TIMEOUT = "TIMEOUT"
AMBIGUOUS = "AMBIGUOUS"
INVALID = "INVALID"

Outcome = Literal["WIN", "LOSS", "TIMEOUT", "AMBIGUOUS", "INVALID"]


@dataclass(frozen=True)
class SignalOutcome:
    event_id: str
    direction: str
    entry: float | None
    stop: float | None
    target: float | None
    outcome: Outcome
    bars_observed: int
    bars_to_resolution: int | None
    resolved_at: object | None
    mfe_r: float | None
    mae_r: float | None


def _validate_candle(raw: dict) -> tuple[float, float]:
    try:
        high = float(raw["high"])
        low = float(raw["low"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("outcome labeling requires numeric candle high/low") from exc
    if not all(isfinite(value) for value in (high, low)):
        raise ValueError("candle high/low must be finite")
    if high < low:
        raise ValueError("candle high must be >= low")
    return high, low


def _validate_positive_finite(value: float, field_name: str) -> None:
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{field_name} must be finite and > 0")


def label_signal_outcome(
    *,
    event_id: str,
    direction: str,
    entry: float,
    stop: float,
    future_candles: list[dict],
    target_r_multiple: float = 2.0,
    max_bars: int = 20,
) -> SignalOutcome:
    """Label a closed paper signal using only candles after its signal bar.

    ``entry`` is the already-emitted signal reference, not a price discovered
    from future candles. ``target_r_multiple`` defines the hypothetical target
    distance from entry using the supplied stop. ``max_bars`` is the observation
    horizon; reaching the horizon without a terminal event is TIMEOUT.

    The caller must provide candles strictly after the signal bar. This keeps
    the function causal and makes accidental same-bar look-ahead explicit.
    """
    if not event_id:
        raise ValueError("event_id must not be empty")
    if direction not in {LONG, SHORT}:
        raise ValueError("direction must be LONG or SHORT")
    _validate_positive_finite(target_r_multiple, "target_r_multiple")
    if isinstance(max_bars, bool) or not isinstance(max_bars, int) or max_bars < 1:
        raise ValueError("max_bars must be an integer >= 1")
    _validate_positive_finite(entry, "entry")
    _validate_positive_finite(stop, "stop")
    if not isinstance(future_candles, list):
        raise ValueError("future_candles must be a list")

    risk = entry - stop if direction == LONG else stop - entry
    if risk <= 0:
        raise ValueError("stop must be beyond entry in the trade direction")

    target = entry + risk * target_r_multiple if direction == LONG else entry - risk * target_r_multiple
    sample = future_candles[:max_bars]
    mfe_r = 0.0
    mae_r = 0.0

    for index, raw in enumerate(sample, start=1):
        high, low = _validate_candle(raw)

        if direction == LONG:
            favorable = (high - entry) / risk
            adverse = (low - entry) / risk
            hit_stop = low <= stop
            hit_target = high >= target
        else:
            favorable = (entry - low) / risk
            adverse = (entry - high) / risk
            hit_stop = high >= stop
            hit_target = low <= target

        mfe_r = max(mfe_r, favorable)
        mae_r = min(mae_r, adverse)

        if hit_stop and hit_target:
            return SignalOutcome(
                event_id, direction, entry, stop, target, AMBIGUOUS,
                index, index, raw.get("time", raw.get("datetime")), mfe_r, mae_r,
            )
        if hit_stop:
            return SignalOutcome(
                event_id, direction, entry, stop, target, LOSS,
                index, index, raw.get("time", raw.get("datetime")), mfe_r, mae_r,
            )
        if hit_target:
            return SignalOutcome(
                event_id, direction, entry, stop, target, WIN,
                index, index, raw.get("time", raw.get("datetime")), mfe_r, mae_r,
            )

    return SignalOutcome(
        event_id, direction, entry, stop, target, TIMEOUT,
        len(sample), None, None, mfe_r, mae_r,
    )


def label_wait_outcome(*, event_id: str, direction: str = WAIT) -> SignalOutcome:
    """Represent a non-directional signal without pretending it was a trade."""
    if not event_id:
        raise ValueError("event_id must not be empty")
    return SignalOutcome(event_id, direction, None, None, None, INVALID, 0, None, None, None, None)


__all__ = [
    "AMBIGUOUS",
    "INVALID",
    "LOSS",
    "LONG",
    "SHORT",
    "SignalOutcome",
    "TIMEOUT",
    "WAIT",
    "WIN",
    "label_signal_outcome",
    "label_wait_outcome",
]
