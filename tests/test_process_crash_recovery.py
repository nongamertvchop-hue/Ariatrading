"""Proof that paper runtime recovery survives a real process death."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def test_process_death_restart_recovers_open_position(tmp_path: Path) -> None:
    checkpoint = tmp_path / "crash.json"
    history = tmp_path / "crash.history.jsonl"
    code = r'''
from strategy.paper_runtime_engine import PaperRuntimeEngine, RuntimeBar, RuntimeSignal

engine = PaperRuntimeEngine(checkpoint_path=r"CHECKPOINT", history_path=r"HISTORY")
engine.start()
engine.process_bar(
    RuntimeBar("2026-01-01T00:00:00+00:00", 1.10, 1.11, 1.09, 1.105),
    RuntimeSignal(action="LONG", entry=1.105, stop=1.100),
)
# Kill the interpreter without normal cleanup: this is an actual process-death test.
import os
os._exit(137)
'''.replace("CHECKPOINT", str(checkpoint)).replace("HISTORY", str(history))

    completed = subprocess.run([sys.executable, "-c", code], check=False)
    assert completed.returncode == 137
    assert checkpoint.exists()
    assert history.exists()

    recovered = __import__("strategy.paper_runtime_engine", fromlist=["PaperRuntimeEngine"]).PaperRuntimeEngine(
        checkpoint_path=checkpoint,
        history_path=history,
    )
    result = recovered.recover()
    assert result.accepted
    assert recovered.lifecycle.value == "OPEN"
    assert recovered.account.position is not None
    assert recovered.last_processed_bar_time == "2026-01-01T00:00:00+00:00"


def test_process_death_preserves_pending_unknown_as_halt(tmp_path: Path) -> None:
    checkpoint = tmp_path / "pending.json"
    history = tmp_path / "pending.history.jsonl"
    code = r'''
from strategy.paper_runtime_engine import FailureMode, PaperRuntimeEngine, RuntimeBar, RuntimeSignal

engine = PaperRuntimeEngine(checkpoint_path=r"CHECKPOINT", history_path=r"HISTORY")
engine.start()
engine.set_failure_mode(FailureMode.TIMEOUT_AFTER_ACCEPT)
engine.process_bar(
    RuntimeBar("2026-01-01T00:05:00+00:00", 1.10, 1.11, 1.09, 1.105),
    RuntimeSignal(action="LONG", entry=1.105, stop=1.100),
)
import os
os._exit(137)
'''.replace("CHECKPOINT", str(checkpoint)).replace("HISTORY", str(history))

    completed = subprocess.run([sys.executable, "-c", code], check=False)
    assert completed.returncode == 137
    recovered = __import__("strategy.paper_runtime_engine", fromlist=["PaperRuntimeEngine"]).PaperRuntimeEngine(
        checkpoint_path=checkpoint,
        history_path=history,
    )
    result = recovered.recover()
    assert not result.accepted
    assert recovered.lifecycle.value == "HALT"
    assert recovered.halt_reason
