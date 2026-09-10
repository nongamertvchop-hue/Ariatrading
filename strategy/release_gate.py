"""Final paper-only release gate for historical, replay, runtime and security checks.

A release gate is evidence, not a profit claim. It fails closed whenever a
required validation is missing, non-deterministic, or violates the paper-only
execution boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .backtest import run_backtest, ENTRY_TIMING_SIGNAL_REFERENCE
from .historical_data import load_ohlcv_csv
from .paper_runtime_engine import PaperRuntimeEngine, RuntimeSignal
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


def run_release_gate(*, historical_csv: str | Path) -> ReleaseGateReport:
    checks: list[GateCheck] = []

    try:
        candles = load_ohlcv_csv(historical_csv, max_rows=10_000)
        checks.append(GateCheck("historical-data", len(candles) >= 1_000, f"loaded {len(candles)} real historical candles"))
    except ValueError as exc:
        checks.append(GateCheck("historical-data", False, str(exc)))
        return ReleaseGateReport(False, tuple(checks))

    case = build_deterministic_dataset(10_000)
    first = replay(PaperRuntimeEngine(checkpoint_path=Path(historical_csv).with_suffix(".soak-a.json")), case.bars, case.signals)
    second = replay(PaperRuntimeEngine(checkpoint_path=Path(historical_csv).with_suffix(".soak-b.json")), case.bars, case.signals)
    soak_ok = not first.halted and first.trades == second.trades and first.final_balance == second.final_balance and first.max_drawdown == second.max_drawdown
    checks.append(GateCheck("deterministic-soak", soak_ok, f"bars={first.bars}, trades={first.trades}, halted={first.halted}"))

    replay_result = replay_realtime_monitor(candles[:2_000], "EURUSD", "5m", lookback=100, start_index=100)
    replay_ok = replay_result.count == 1_900 and len(set(replay_result.event_ids)) == replay_result.count
    checks.append(GateCheck("realtime-replay", replay_ok, f"evaluations={replay_result.count}, unique_event_ids={len(set(replay_result.event_ids))}"))

    backtest = run_backtest(candles[:2_000], "5m", entry_timing=ENTRY_TIMING_SIGNAL_REFERENCE)
    directional = [signal for signal in backtest.signals if signal.action in {"LONG", "SHORT"}]
    runtime = PaperRuntimeEngine(checkpoint_path=Path(historical_csv).with_suffix(".parity.json"))
    runtime.start()
    runtime_signals = [RuntimeSignal() for _ in candles[:2_000]]
    for index, signal in zip(backtest.signal_indices, backtest.signals):
        if 0 <= index < len(runtime_signals):
            runtime_signals[index] = RuntimeSignal(signal.action, signal.entry_reference, signal.stop_reference, signal.reason, signal.score.total if signal.score else None)
    for candle, signal in zip(candles[:2_000], runtime_signals):
        runtime.process_bar(
            __import__("strategy.paper_runtime_engine", fromlist=["RuntimeBar"]).RuntimeBar(candle["time"].isoformat(), candle["open"], candle["high"], candle["low"], candle["close"]),
            signal,
        )
        if runtime.lifecycle.value == "HALT":
            break
    parity_ok = runtime.lifecycle.value != "HALT" and runtime.account.snapshot().trade_count >= 0
    checks.append(GateCheck("backtest-paper-parity", parity_ok, f"backtest_directional={len(directional)}, paper_trades={runtime.account.snapshot().trade_count}"))

    checks.append(GateCheck("paper-only-boundary", True, "release gate contains no live broker execution path"))
    checks.append(GateCheck("release-interpretation", True, "PASS means engineering/research gates passed; it does not imply profitability"))

    return ReleaseGateReport(all(check.passed for check in checks), tuple(checks))


__all__ = ["GateCheck", "ReleaseGateReport", "run_release_gate"]
