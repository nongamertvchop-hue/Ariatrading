from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from strategy.journal import JournalEvent
from strategy.paper import CLOSED, PaperPosition
from strategy.paper_session import PaperSessionResult
from strategy.paired_analysis import analyze_paired_paper_outcomes


def _result(time, event_id, action="LONG"):
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
    return PaperSessionResult(
        evaluation=SimpleNamespace(symbol="TEST", timeframe="1m", bar_time=time, signal=SimpleNamespace(action=action)),
        opened=None,
        closed=None,
        signal_event=event,
        open_event=None,
        close_event=None,
    )


def _closed_position(signal_time, trade_id, r_multiple):
    entry_time = signal_time + timedelta(minutes=1)
    exit_time = signal_time + timedelta(minutes=2)
    return PaperPosition(
        trade_id=trade_id,
        direction="LONG",
        signal_time=signal_time,
        entry_time=entry_time,
        entry_price=100.0,
        stop=99.0,
        target=102.0,
        risk_distance=1.0,
        status=CLOSED,
        exit_time=exit_time,
        exit_price=102.0,
        outcome="WIN" if r_multiple > 0 else "LOSS",
        r_multiple=r_multiple,
        bars_held=1,
    )


def _closed_replay(start, prefix, r_multiple):
    signal = _result(start, f"{prefix}-signal")
    opened = _result(start + timedelta(minutes=1), f"{prefix}-open", action="WAIT")
    closed = _result(start + timedelta(minutes=2), f"{prefix}-close", action="WAIT")
    position = _closed_position(start, int(prefix.split("-")[-1]), r_multiple)
    return [signal, replace(opened, opened=position), replace(closed, closed=position)]


def test_identical_arms_have_zero_paired_delta():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    baseline = _closed_replay(start, "trade-1", 2.0)
    mtf = _closed_replay(start, "trade-101", 2.0)

    analysis = analyze_paired_paper_outcomes(baseline, mtf, bootstrap_samples=100)

    assert analysis.paired_count == 1
    assert analysis.resolved_pair_count == 1
    assert analysis.realized_r_delta == 0.0
    assert analysis.mean_r_delta == 0.0
    assert analysis.ci_available is False


def test_filtered_wait_is_paired_as_zero_r():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    baseline = _closed_replay(start, "trade-1", 2.0)
    mtf = [_result(start, "mtf-wait", action="WAIT"), _result(start + timedelta(minutes=1), "mtf-next", action="WAIT")]

    analysis = analyze_paired_paper_outcomes(baseline, mtf, bootstrap_samples=100)

    assert analysis.paired_count == 1
    assert analysis.mtf_signal_count == 0
    assert analysis.realized_r_delta == -2.0
    assert analysis.mean_r_delta == -2.0


def test_bootstrap_confidence_interval_is_deterministic():
    baseline = []
    mtf = []
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for index in range(20):
        time = start + timedelta(minutes=index * 5)
        baseline.extend(_closed_replay(time, f"trade-{index}", 1.0))
        mtf.extend(_closed_replay(time, f"trade-{100 + index}", 2.0))

    first = analyze_paired_paper_outcomes(baseline, mtf, random_seed=42, bootstrap_samples=1000)
    second = analyze_paired_paper_outcomes(baseline, mtf, random_seed=42, bootstrap_samples=1000)

    assert first.ci_available is True
    assert first.mean_r_delta == 1.0
    assert first.bootstrap_ci_low == second.bootstrap_ci_low
    assert first.bootstrap_ci_high == second.bootstrap_ci_high


def test_unresolved_pairs_are_excluded_from_statistics():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    baseline = [_result(start, "baseline-final")]
    mtf = [_result(start, "mtf-final")]

    analysis = analyze_paired_paper_outcomes(baseline, mtf)

    assert analysis.paired_count == 1
    assert analysis.resolved_pair_count == 0
    assert analysis.mean_r_delta is None
    assert analysis.ci_available is False


def test_missing_mtf_opportunity_is_rejected():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    baseline = _closed_replay(start, "trade-1", 1.0)
    mtf = [_result(start + timedelta(minutes=1), "mtf-other", action="WAIT")]

    try:
        analyze_paired_paper_outcomes(baseline, mtf)
    except ValueError as exc:
        assert "missing a result" in str(exc)
    else:
        raise AssertionError("expected missing MTF opportunity to fail")
