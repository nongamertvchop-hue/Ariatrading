from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from strategy.engine import EngineSignal, LONG, SHORT
from strategy.journal import JournalEvent
from strategy.paper_outcomes import PaperSignalOutcome, SKIPPED, WIN
from strategy.paper_session import PaperSessionResult
from strategy.scoring import SetupScore
from strategy.signal_quality import build_signal_quality_report


@dataclass
class _Result:
    evaluation: object
    signal_event: JournalEvent


def _candles(count=10):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        {
            "time": start + timedelta(minutes=15 * i),
            "open": 100.0 + i * 0.1,
            "high": 100.5 + i * 0.1,
            "low": 99.5 + i * 0.1,
            "close": 100.2 + i * 0.1,
        }
        for i in range(count)
    ]


def _result(event_id, index, action, breakout, score):
    bar_time = _candles()[index]["time"]
    event = JournalEvent(
        event_time=bar_time,
        event_type="SIGNAL",
        symbol="TEST",
        timeframe="15m",
        action=action,
        reason="setup",
        event_id=event_id,
        signal_time=bar_time,
    )
    signal = EngineSignal(
        action=action,
        reason="setup",
        timeframe="15m",
        breakout_state=breakout,
        score=SetupScore(score, 10, 10, 20, 20, 0, ()),
    )
    evaluation = SimpleNamespace(symbol="TEST", timeframe="15m", bar_time=bar_time, signal=signal)
    return PaperSessionResult(
        evaluation=evaluation,
        opened=None,
        closed=None,
        signal_event=event,
        open_event=None,
        close_event=None,
    )


def test_report_groups_by_timeframe_breakout_and_score():
    results = (
        _result("s1", 5, LONG, "NO_BREAKOUT", 75),
        _result("s2", 6, SHORT, "FAKE_BREAKOUT", 45),
    )
    outcomes = (
        PaperSignalOutcome("s1", "TEST", "15m", results[0].evaluation.bar_time, LONG, WIN, trade_id=1, r_multiple=2.0),
        PaperSignalOutcome("s2", "TEST", "15m", results[1].evaluation.bar_time, SHORT, SKIPPED),
    )

    report = build_signal_quality_report(results, outcomes, {"15m": _candles()})

    assert len(report.by_timeframe) == 1
    assert report.by_timeframe[0].signals == 2
    assert report.by_timeframe[0].wins == 1
    assert report.by_timeframe[0].skipped == 1
    assert report.by_timeframe[0].realized_r == 2.0
    assert {row.value for row in report.by_breakout_state} == {"NO_BREAKOUT", "FAKE_BREAKOUT"}
    assert {row.value for row in report.by_score_bucket} == {"40-59", "60-79"}


def test_regime_uses_signal_prefix_not_future_candles():
    candles = _candles()
    result = _result("s1", 5, LONG, "NO_BREAKOUT", 75)
    outcome = PaperSignalOutcome(
        "s1", "TEST", "15m", result.evaluation.bar_time, LONG, SKIPPED,
    )

    first = build_signal_quality_report((result,), (outcome,), {"15m": candles})
    modified = [dict(candle) for candle in candles]
    modified[-1]["high"] = 999.0
    modified[-1]["low"] = 998.0
    modified[-1]["open"] = 998.5
    modified[-1]["close"] = 998.8
    second = build_signal_quality_report((result,), (outcome,), {"15m": modified})

    assert first.by_regime == second.by_regime


def test_report_rejects_missing_outcome():
    result = _result("s1", 5, LONG, "NO_BREAKOUT", 75)

    try:
        build_signal_quality_report((result,), (), {"15m": _candles()})
    except ValueError as exc:
        assert "same directional signal IDs" in str(exc)
    else:
        raise AssertionError("missing outcome must fail closed")
