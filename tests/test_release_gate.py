from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from strategy.paper_history import PaperHistoryError, PaperHistoryStore
from strategy.paper_runtime_engine import FailureMode, PaperRuntimeEngine, RuntimeBar, RuntimeSignal, RuntimeLifecycle
from strategy.release_gate import run_release_gate


def make_bar(time: str, price: float) -> RuntimeBar:
    return RuntimeBar(time, price, price + 0.5, price - 0.5, price)


def test_long_term_history_is_append_only_and_detects_tampering(tmp_path: Path):
    engine = PaperRuntimeEngine(checkpoint_path=tmp_path / "runtime.json")
    engine.start()
    engine.process_bar(make_bar("1", 100), RuntimeSignal())
    history = PaperHistoryStore(tmp_path / "runtime.history.jsonl")
    records = history.verify()
    assert len(records) == 1
    path = tmp_path / "runtime.history.jsonl"
    path.write_text(path.read_text(encoding="utf-8").replace('"equity":10000.0', '"equity":9999.0', 1), encoding="utf-8")
    try:
        history.verify()
    except PaperHistoryError as exc:
        assert "hash mismatch" in str(exc)
    else:
        raise AssertionError("tampered history must fail closed")


def test_hard_process_termination_leaves_pending_checkpoint_for_restart_recovery(tmp_path: Path):
    checkpoint = tmp_path / "crash.json"
    code = (
        "from strategy.paper_runtime_engine import PaperRuntimeEngine, FailureMode, RuntimeBar, RuntimeSignal; "
        f"e=PaperRuntimeEngine(checkpoint_path=r'{checkpoint}'); "
        "e.set_failure_mode(FailureMode.TIMEOUT_AFTER_ACCEPT); e.start(); "
        "e.process_bar(RuntimeBar('1',100,100.5,99.5,100), RuntimeSignal('LONG',100,95,'crash')); "
        "import os; os._exit(137)"
    )
    child = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1])
    assert child.returncode == 137
    recovered = PaperRuntimeEngine(checkpoint_path=checkpoint).recover()
    assert recovered.lifecycle is RuntimeLifecycle.HALT
    assert "pending paper order" in recovered.reason


def test_release_gate_uses_real_market_fixture_when_configured():
    csv_path = os.getenv("ARIATRADING_HISTORICAL_CSV")
    if not csv_path:
        return
    report = run_release_gate(historical_csv=csv_path)
    assert report.passed, "release gate failed: " + "; ".join(f"{c.name}: {c.detail}" for c in report.checks if not c.passed)
