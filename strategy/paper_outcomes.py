"""Leakage-safe outcome labels for historical paper signals.

Labels are derived only from lifecycle events that occur after a signal's
closed-candle decision. The signal itself is never modified and no future bar
is exposed to the realtime decision engine.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from .paper_session import PaperSessionResult


WIN = "WIN"
LOSS = "LOSS"
SKIPPED = "SKIPPED"
UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class PaperSignalOutcome:
    """Outcome label for one directional paper signal."""

    event_id: str
    symbol: str
    timeframe: str
    signal_time: datetime
    action: str
    outcome: str
    trade_id: int | None = None
    exit_time: datetime | None = None
    r_multiple: float | None = None
    bars_held: int | None = None


def label_paper_signals(
    results: Sequence[PaperSessionResult],
) -> tuple[PaperSignalOutcome, ...]:
    """Label directional paper signals using only later paper lifecycle data.

    A signal that is opened and later closed receives WIN/LOSS from the paper
    engine's recorded close event. A directional signal that was never opened
    is SKIPPED, except for a signal on the final replay candle, which remains
    UNRESOLVED because its required next bar was never observed. An opened
    position that remains open when replay ends is also UNRESOLVED. WAIT signals
    are excluded because they are not trade candidates.
    """
    if not results:
        return ()

    signal_rows = {
        result.signal_event.event_id: result
        for result in results
        if result.signal_event.action in {"LONG", "SHORT"}
        and result.signal_event.event_id is not None
    }

    signal_by_time = {
        (result.evaluation.symbol, result.evaluation.timeframe, result.evaluation.bar_time): result.signal_event.event_id
        for result in results
        if result.signal_event.action in {"LONG", "SHORT"}
        and result.signal_event.event_id is not None
    }

    opened_trade_to_signal: dict[int, str] = {}
    closed_trade: dict[int, PaperSessionResult] = {}
    for result in results:
        if result.opened is not None:
            event_id = signal_by_time.get(
                (result.evaluation.symbol, result.evaluation.timeframe, result.opened.signal_time)
            )
            if event_id is None:
                raise ValueError("paper replay opened trade has no matching signal event")
            opened_trade_to_signal[result.opened.trade_id] = event_id
        if result.closed is not None:
            closed_trade[result.closed.trade_id] = result

    signal_to_trade = {event_id: trade_id for trade_id, event_id in opened_trade_to_signal.items()}
    labels: list[PaperSignalOutcome] = []
    final_result = results[-1]

    for event_id, result in signal_rows.items():
        signal_event = result.signal_event
        trade_id = signal_to_trade.get(event_id)
        if trade_id is None:
            outcome = UNRESOLVED if result is final_result else SKIPPED
            labels.append(
                PaperSignalOutcome(
                    event_id=event_id,
                    symbol=signal_event.symbol,
                    timeframe=signal_event.timeframe,
                    signal_time=signal_event.signal_time.astimezone(timezone.utc),
                    action=signal_event.action,
                    outcome=outcome,
                )
            )
            continue

        close_result = closed_trade.get(trade_id)
        if close_result is None:
            labels.append(
                PaperSignalOutcome(
                    event_id=event_id,
                    symbol=signal_event.symbol,
                    timeframe=signal_event.timeframe,
                    signal_time=signal_event.signal_time.astimezone(timezone.utc),
                    action=signal_event.action,
                    outcome=UNRESOLVED,
                    trade_id=trade_id,
                )
            )
            continue

        closed = close_result.closed
        if closed is None:
            raise ValueError("closed trade result is missing its closed position")
        if closed.exit_time is None or closed.exit_time <= signal_event.signal_time:
            raise ValueError("paper outcome close must occur after signal time")
        if closed.outcome not in {WIN, LOSS}:
            raise ValueError("paper outcome must be WIN or LOSS")
        labels.append(
            PaperSignalOutcome(
                event_id=event_id,
                symbol=signal_event.symbol,
                timeframe=signal_event.timeframe,
                signal_time=signal_event.signal_time.astimezone(timezone.utc),
                action=signal_event.action,
                outcome=closed.outcome,
                trade_id=trade_id,
                exit_time=closed.exit_time,
                r_multiple=closed.r_multiple,
                bars_held=closed.bars_held,
            )
        )

    return tuple(labels)


__all__ = [
    "WIN",
    "LOSS",
    "SKIPPED",
    "UNRESOLVED",
    "PaperSignalOutcome",
    "label_paper_signals",
]
