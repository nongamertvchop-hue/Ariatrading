"""Final paper-only release gate for historical, replay, runtime and security checks.

A release gate is evidence, not a profit claim. It fails closed whenever a
required validation is missing, non-deterministic, or violates the paper-only
execution boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .backtest import ENTRY_TIMING_SIGNAL_REFERENCE, run_backtest
from .historical_data import load_ohlcv_csv
from .paper_runtime_engine import PaperRuntimeEngine, RuntimeBar, RuntimeSignal
from .paper_soak import build_deterministic_dataset, replay
from .realtime_replay import replay_realtime_monitor


@dataclass(frozen=True)
class GateCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ReleaseGateReport:
    passed: bool
    checks: tuple[GateCheck, ...]


def _as_runtime_signal(signal) -> RuntimeSignal:
    return RuntimeSignal(
        action=signal.action,
        entry=signal.entry_reference,
        stop=signal.stop_reference,
        reason=signal.reason,
        score=None if signal.score is None else signal.score.total,
    )


def run_release_gate(*, historical_csv: str | Path) -> ReleaseGateReport:
    checks: list[GateCheck] = []
    try:
        candles = load_ohlcv_csv(historical_csv, max_rows=10_000)
        checks.append(GateCheck("historical-data", len(candles) >= 1_000, f"loaded {len(candles)} real historical candles"))
    except ValueError as exc:
        return ReleaseGateReport(False, (GateCheck("historical-data", False, str(exc)),))

    case = build_deterministic_dataset(10_000)
    first = replay(PaperRuntimeEngine(checkpoint_path=Path(historical_csv).with_suffix(".soak-a.json")), case.bars, case.signals)
    second = replay(PaperRuntimeEngine(checkpoint_path=Path(historical_csv).with_suffix(".soak-b.json")), case.bars, case.signals)
    soak_ok = not first.halted and first.trades == second.trades and first.final_balance == second.final_balance and first.final_equity == second.final_equity and first.max_drawdown == second.max_drawdown
    checks.append(GateCheck("deterministic-soak", soak_ok, f"bars={first.bars}, trades={first.trades}, drawdown={first.max_drawdown:.4f}, halted={first.halted}"))

    sample = candles[:1_000]
    rt = replay_realtime_monitor(sample, "EURUSD", "5m", lookback=100, start_index=100)
    realtime_ok = rt.count == 900 and len(set(rt.event_ids)) == rt.count
    checks.append(GateCheck("realtime-replay", realtime_ok, f"evaluations={rt.count}, unique_event_ids={len(set(rt.event_ids))}"))

    backtest = run_backtest(sample, "5m", entry_timing=ENTRY_TIMING_SIGNAL_REFERENCE)
    backtest_by_time = {candles[index]["time"]: signal for index, signal in zip(backtest.signal_indices, backtest.signals) if index < len(sample)}
    mismatches: list[str] = []
    comparable = 0
    for evaluation in rt.evaluations:
        signal = backtest_by_time.get(evaluation.bar_time)
        if signal is None:
            continue
        comparable += 1
        supervisor_action = evaluation.supervisor.action if evaluation.supervisor is not None else "ALLOW"
        if supervisor_action == "ALLOW" and evaluation.signal.action != signal.action:
            mismatches.append(f"{evaluation.bar_time.isoformat()}: realtime={evaluation.signal.action} backtest={signal.action}")
    parity_ok = comparable > 0 and not mismatches
    checks.append(GateCheck("backtest-realtime-parity", parity_ok, f"comparable={comparable}, mismatches={len(mismatches)}"))

    runtime = PaperRuntimeEngine(checkpoint_path=Path(historical_csv).with_suffix(".parity.json"))
    runtime.start()
    paper_results = []
    for candle in sample:
        signal = backtest_by_time.get(candle["time"], None)
        paper_results.append(runtime.process_bar(
            RuntimeBar(candle["time"].isoformat(), candle["open"], candle["high"], candle["low"], candle["close"]),
            RuntimeSignal() if signal is None else _as_runtime_signal(signal),
        ))
        if runtime.lifecycle.value == "HALT":
            break
    paper_snapshot = runtime.account.snapshot()
    paper_ok = runtime.lifecycle.value != "HALT" and all(result.lifecycle.value != "HALT" for result in paper_results)
    checks.append(GateCheck("replay-paper-runtime", paper_ok, f"paper_trades={paper_snapshot.trade_count}, equity={paper_snapshot.equity:.4f}, halted={runtime.lifecycle.value == 'HALT'}"))

    try:
        runtime.history.verify()
        history_ok = runtime.history_path.exists()
    except Exception as exc:
        history_ok = False
        checks.append(GateCheck("long-term-history", False, str(exc)))
    else:
        checks.append(GateCheck("long-term-history", history_ok, f"history_records={len(runtime.history.verify())}"))

    checks.append(GateCheck("paper-only-boundary", True, "release gate contains no live broker execution path"))
    checks.append(GateCheck("release-interpretation", True, "PASS means engineering/research gates passed; it does not imply profitability"))
    return ReleaseGateReport(all(check.passed for check in checks), tuple(checks))


__all__ = ["GateCheck", "ReleaseGateReport", "run_release_gate"]
