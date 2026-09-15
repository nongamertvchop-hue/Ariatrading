"""Three-way parity certification for backtest, realtime replay and paper runtime.

The certificate compares one immutable decision stream across all three paths.
It does not authorize broker execution and never talks to a live broker.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from pathlib import Path
from typing import Sequence

from .backtest import ENTRY_TIMING_SIGNAL_REFERENCE, run_backtest
from .paper_runtime_engine import PaperRuntimeEngine, RuntimeBar, RuntimeLifecycle, RuntimeSignal
from .realtime_replay import replay_realtime_monitor


@dataclass(frozen=True)
class DecisionRecord:
    bar_time: str
    action: str
    entry: float | None
    stop: float | None
    event_id: str


@dataclass(frozen=True)
class ParityCertificate:
    passed: bool
    candles: int
    compared: int
    mismatches: tuple[str, ...]
    backtest_fingerprint: str
    realtime_fingerprint: str
    paper_fingerprint: str
    paper_trades: int
    paper_balance: float
    paper_equity: float
    paper_drawdown: float

    def as_dict(self) -> dict:
        return asdict(self)


def _fingerprint(records: Sequence[DecisionRecord]) -> str:
    """Fingerprint decision semantics, intentionally excluding event IDs."""
    payload = json.dumps(
        [{"bar_time": r.bar_time, "action": r.action, "entry": r.entry, "stop": r.stop} for r in records],
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def _validate_stream(name: str, records: Sequence[DecisionRecord]) -> tuple[str, ...]:
    """Validate ordering and uniqueness before any dict-based comparison."""
    findings: list[str] = []
    seen: set[str] = set()
    previous: str | None = None
    for index, record in enumerate(records):
        if record.bar_time in seen:
            findings.append(f"{name}: duplicate decision timestamp at index {index}: {record.bar_time}")
        seen.add(record.bar_time)
        if previous is not None and record.bar_time <= previous:
            findings.append(
                f"{name}: decision timestamps are not strictly increasing at index {index}: "
                f"previous={previous}, current={record.bar_time}"
            )
        previous = record.bar_time
    return tuple(findings)


def _backtest_records(candles: Sequence[dict], timeframe: str) -> tuple[DecisionRecord, ...]:
    result = run_backtest(list(candles), timeframe, entry_timing=ENTRY_TIMING_SIGNAL_REFERENCE)
    return tuple(
        DecisionRecord(
            bar_time=candles[index]["time"].isoformat(),
            action=signal.action,
            entry=signal.entry_reference,
            stop=signal.stop_reference,
            event_id=f"bar:{candles[index]['time'].isoformat()}:{timeframe}",
        )
        for index, signal in zip(result.signal_indices, result.signals)
    )


def _realtime_records(candles: Sequence[dict], symbol: str, timeframe: str, *, start_index: int) -> tuple[DecisionRecord, ...]:
    replay = replay_realtime_monitor(candles, symbol, timeframe, lookback=100, start_index=start_index)
    return tuple(
        DecisionRecord(
            bar_time=evaluation.bar_time.isoformat(),
            action=evaluation.signal.action,
            entry=evaluation.signal.entry_reference,
            stop=evaluation.signal.stop_reference,
            event_id=evaluation.event_id,
        )
        for evaluation in replay.evaluations
    )


def _paper_replay(candles: Sequence[dict], realtime_records: Sequence[DecisionRecord], checkpoint_path: Path):
    by_time = {record.bar_time: record for record in realtime_records}
    runtime = PaperRuntimeEngine(checkpoint_path=checkpoint_path)
    runtime.start()
    consumed: list[DecisionRecord] = []
    for candle in candles:
        key = candle["time"].isoformat()
        record = by_time.get(key)
        signal = RuntimeSignal() if record is None else RuntimeSignal(action=record.action, entry=record.entry, stop=record.stop)
        result = runtime.process_bar(
            RuntimeBar(key, float(candle["open"]), float(candle["high"]), float(candle["low"]), float(candle["close"])),
            signal,
        )
        if record is not None:
            consumed.append(record)
        if result.lifecycle is RuntimeLifecycle.HALT:
            break
    snapshot = runtime.account.snapshot()
    return runtime, tuple(consumed), snapshot


def certify_three_way_parity(*, candles: Sequence[dict], symbol: str, timeframe: str, checkpoint_path: str | Path, start_index: int | None = None) -> ParityCertificate:
    """Create a deterministic certificate over the canonical decision stream.

    The certificate fails closed if either source stream is duplicated, out of
    order, or contains a decision missing from the other stream. Dicts are used
    only after these invariants have been checked, so a duplicate timestamp can
    never be silently overwritten.
    """
    if not candles:
        return ParityCertificate(False, 0, 0, ("no candles supplied",), "", "", "", 0, 0.0, 0.0, 0.0)
    first = max(102, 0 if start_index is None else start_index)
    if first >= len(candles):
        raise ValueError("start_index leaves no replay candles")

    bt = _backtest_records(candles, timeframe)
    rt = _realtime_records(candles, symbol, timeframe, start_index=first)

    mismatches: list[str] = []
    mismatches.extend(_validate_stream("backtest", bt))
    mismatches.extend(_validate_stream("realtime", rt))

    bt_times = [record.bar_time for record in bt]
    rt_times = [record.bar_time for record in rt]
    bt_time_set = set(bt_times)
    rt_time_set = set(rt_times)
    missing_from_rt = sorted(bt_time_set - rt_time_set)
    missing_from_bt = sorted(rt_time_set - bt_time_set)
    mismatches.extend(f"backtest decision missing from realtime: {bar_time}" for bar_time in missing_from_rt)
    mismatches.extend(f"realtime decision missing from backtest: {bar_time}" for bar_time in missing_from_bt)

    bt_by_time = {record.bar_time: record for record in bt}
    rt_by_time = {record.bar_time: record for record in rt}
    common_rt: list[DecisionRecord] = []
    common_bt: list[DecisionRecord] = []
    for realtime in rt:
        backtest = bt_by_time.get(realtime.bar_time)
        if backtest is None:
            continue
        common_rt.append(realtime)
        common_bt.append(backtest)
        if (backtest.action, backtest.entry, backtest.stop) != (realtime.action, realtime.entry, realtime.stop):
            mismatches.append(
                f"{realtime.bar_time}: backtest={(backtest.action, backtest.entry, backtest.stop)!r} "
                f"realtime={(realtime.action, realtime.entry, realtime.stop)!r}"
            )

    compared = len(common_rt)
    runtime, consumed, snapshot = _paper_replay(candles, rt, Path(checkpoint_path))
    consumed_key = tuple((r.bar_time, r.action, r.entry, r.stop) for r in consumed)
    realtime_key = tuple((r.bar_time, r.action, r.entry, r.stop) for r in rt)
    if consumed_key != realtime_key:
        mismatches.append("paper runtime did not consume the exact realtime decision stream")

    backtest_fp = _fingerprint(common_bt)
    realtime_fp = _fingerprint(common_rt)
    paper_fp = _fingerprint(consumed)
    if backtest_fp != realtime_fp or realtime_fp != paper_fp:
        mismatches.append("decision fingerprints differ across backtest/realtime/paper")
    if runtime.lifecycle is RuntimeLifecycle.HALT:
        mismatches.append(f"paper runtime halted: {runtime.halt_reason}")

    return ParityCertificate(
        passed=compared > 0 and not mismatches,
        candles=len(candles),
        compared=compared,
        mismatches=tuple(mismatches[:50]),
        backtest_fingerprint=backtest_fp,
        realtime_fingerprint=realtime_fp,
        paper_fingerprint=paper_fp,
        paper_trades=snapshot.trade_count,
        paper_balance=snapshot.balance,
        paper_equity=snapshot.equity,
        paper_drawdown=snapshot.drawdown,
    )


__all__ = ["DecisionRecord", "ParityCertificate", "certify_three_way_parity"]
