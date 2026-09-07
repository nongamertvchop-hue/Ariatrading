from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from strategy.journal import JournalEvent
from strategy.paper import CLOSED, OPEN, PaperPosition
from strategy.paper_outcomes import SKIPPED, UNRESOLVED, WIN, label_paper_signals
from strategy.paper_session import PaperSessionResult


def _signal_result(time, event_id, action="LONG"):
    event = JournalEvent(
        event_time=time,
        event_type="SIGNAL",
        symbol="TEST",
        timeframe="1m",
        action=action,
        reason="test",
        event_id=event_id,
        signal_time=time,
    )
    evaluation = SimpleNamespace(symbol="TEST", timeframe="1m", bar_time=time)
    return PaperSessionResult(
        evaluation=evaluation,
        opened=None,
        closed=None,
        signal_event=event,
        open_event=None,
        close_event=None,
    )


def _position(signal_time, entry_time, *, status=OPEN, outcome=OPEN, trade_id=1, exit_time=None):
    return PaperPosition(
        trade_id=trade_id,
        direction="LONG",
        signal_time=signal_time,
        entry_time=entry_time,
        entry_price=100.0,
        stop=99.0,
        target=102.0,
        risk_distance=1.0,
        status=status,
        exit_time=exit_time,
        exit_price=102.0 if status == CLOSED else None,
        outcome=outcome,
        r_multiple=2.0 if status == CLOSED else 0.0,
        bars_held=2 if status == CLOSED else 0,
    )


def test_closed_signal_gets_future_win_label():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    signal = _signal_result(start, "signal-1")
    opened = _signal_result(start + timedelta(minutes=1), "wait-1", action="WAIT")
    opened = replace(opened, opened=_position(start, start + timedelta(minutes=1)))
    closed = _signal_result(start + timedelta(minutes=3), "wait-2", action="WAIT")
    closed = replace(
        closed,
        closed=_position(
            start,
            start + timedelta(minutes=1),
            status=CLOSED,
            outcome=WIN,
            exit_time=start + timedelta(minutes=3),
        ),
    )

    labels = label_paper_signals([signal, opened, closed])

    assert labels[0].outcome == WIN
    assert labels[0].trade_id == 1
    assert labels[0].exit_time == start + timedelta(minutes=3)
    assert labels[0].r_multiple == 2.0


def test_final_signal_without_next_bar_is_unresolved():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = _signal_result(start, "signal-final")

    labels = label_paper_signals([result])

    assert labels[0].outcome == UNRESOLVED
    assert labels[0].trade_id is None


def test_directional_signal_not_opened_before_replay_end_is_skipped():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    first = _signal_result(start, "signal-skipped")
    later = _signal_result(start + timedelta(minutes=1), "wait-event", action="WAIT")

    labels = label_paper_signals([first, later])

    assert labels[0].outcome == SKIPPED
