from types import SimpleNamespace

from strategy import parity_certification as parity
from strategy.paper_runtime_engine import RuntimeLifecycle


def _record(timestamp: str, action: str = "WAIT") -> parity.DecisionRecord:
    return parity.DecisionRecord(
        bar_time=timestamp,
        action=action,
        entry=None,
        stop=None,
        event_id=f"evt:{timestamp}",
    )


def _paper_stub(records):
    snapshot = SimpleNamespace(
        trade_count=0,
        balance=10_000.0,
        equity=10_000.0,
        drawdown=0.0,
    )
    runtime = SimpleNamespace(lifecycle=RuntimeLifecycle.OPEN, halt_reason=None)
    return runtime, tuple(records), snapshot


def test_parity_fails_closed_on_duplicate_realtime_timestamp(monkeypatch, tmp_path):
    candles = [{"time": SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00+00:00")}] * 3
    bt = (_record("2026-01-01T00:00:00+00:00"),)
    rt = (
        _record("2026-01-01T00:00:00+00:00"),
        _record("2026-01-01T00:00:00+00:00"),
    )
    monkeypatch.setattr(parity, "_backtest_records", lambda *_: bt)
    monkeypatch.setattr(parity, "_realtime_records", lambda *_args, **_kwargs: rt)
    monkeypatch.setattr(parity, "_paper_replay", lambda *_args: _paper_stub(rt))

    certificate = parity.certify_three_way_parity(
        candles=candles,
        symbol="EURUSD",
        timeframe="5m",
        checkpoint_path=tmp_path / "runtime.json",
        start_index=0,
    )

    assert not certificate.passed
    assert any("duplicate decision timestamp" in item for item in certificate.mismatches)


def test_parity_fails_closed_when_backtest_has_unmatched_decision(monkeypatch, tmp_path):
    candles = [{"time": SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00+00:00")}] * 3
    bt = (
        _record("2026-01-01T00:00:00+00:00"),
        _record("2026-01-01T00:05:00+00:00"),
    )
    rt = (_record("2026-01-01T00:00:00+00:00"),)
    monkeypatch.setattr(parity, "_backtest_records", lambda *_: bt)
    monkeypatch.setattr(parity, "_realtime_records", lambda *_args, **_kwargs: rt)
    monkeypatch.setattr(parity, "_paper_replay", lambda *_args: _paper_stub(rt))

    certificate = parity.certify_three_way_parity(
        candles=candles,
        symbol="EURUSD",
        timeframe="5m",
        checkpoint_path=tmp_path / "runtime.json",
        start_index=0,
    )

    assert not certificate.passed
    assert any("backtest decision missing from realtime" in item for item in certificate.mismatches)
