"""Final paper-only release gate for historical, parity, runtime and security checks.

A release gate is evidence, not a profit claim. It fails closed whenever a
required validation is missing, non-deterministic, or violates the paper-only
execution boundary.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile

from .historical_data import load_ohlcv_csv
from .paper_boundary import verify_paper_boundary
from .paper_soak import build_deterministic_dataset, replay
from .paper_runtime_engine import PaperRuntimeEngine
from .parity_certification import certify_three_way_parity
from .historical_shadow import run_long_shadow


class GateCheck:
    def __init__(self, name: str, passed: bool, detail: str):
        self.name, self.passed, self.detail = name, bool(passed), str(detail)

    def __repr__(self):
        return f"GateCheck({self.name!r}, {self.passed!r}, {self.detail!r})"


class ReleaseGateReport:
    def __init__(self, passed: bool, checks: tuple[GateCheck, ...]):
        self.passed, self.checks = bool(passed), tuple(checks)


def _process_crash_restart_check() -> tuple[bool, str]:
    """Kill a real child interpreter and verify a fresh process can recover it."""
    with tempfile.TemporaryDirectory(prefix="aria-crash-gate-") as temp:
        root = Path(temp)
        checkpoint, history = root / "runtime.json", root / "runtime.history.jsonl"
        code = f'''
from strategy.paper_runtime_engine import PaperRuntimeEngine, RuntimeBar, RuntimeSignal
engine = PaperRuntimeEngine(checkpoint_path=r"{checkpoint}", history_path=r"{history}")
engine.start()
engine.process_bar(RuntimeBar("2026-01-01T00:00:00+00:00",1.10,1.11,1.09,1.105), RuntimeSignal("LONG",1.105,1.100,"crash"))
import os
os._exit(137)
'''
        child = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1], check=False)
        if child.returncode != 137 or not checkpoint.exists() or not history.exists():
            return False, f"child_exit={child.returncode}, checkpoint={checkpoint.exists()}, history={history.exists()}"
        recovered = PaperRuntimeEngine(checkpoint_path=checkpoint, history_path=history)
        result = recovered.recover()
        ok = result.accepted and recovered.lifecycle.value == "OPEN" and recovered.account.position is not None
        return ok, f"child_exit={child.returncode}, lifecycle={recovered.lifecycle.value}, position={recovered.account.position is not None}"


def _paper_config_check() -> tuple[bool, str]:
    try:
        from bot.config import BotConfig
        BotConfig(mode="live").validate()
    except RuntimeError as exc:
        return True, str(exc)
    return False, "BotConfig accepted live mode"


def run_release_gate(*, historical_csv: str | Path) -> ReleaseGateReport:
    checks: list[GateCheck] = []

    boundary_ok, boundary_findings = verify_paper_boundary()
    checks.append(GateCheck("paper-only-boundary", boundary_ok, "paper path isolated from live execution" if boundary_ok else "; ".join(boundary_findings)))

    config_ok, config_detail = _paper_config_check()
    checks.append(GateCheck("paper-only-config", config_ok, config_detail))

    try:
        candles = load_ohlcv_csv(historical_csv, max_rows=10_000)
        schema_ok = len(candles) >= 1_000
        checks.append(GateCheck("historical-data", schema_ok, f"loaded {len(candles)} real historical candles"))
    except ValueError as exc:
        return ReleaseGateReport(False, tuple(checks + [GateCheck("historical-data", False, str(exc))]))

    case = build_deterministic_dataset(10_000)
    first = replay(PaperRuntimeEngine(checkpoint_path=Path(historical_csv).with_suffix(".soak-a.json")), case.bars, case.signals)
    second = replay(PaperRuntimeEngine(checkpoint_path=Path(historical_csv).with_suffix(".soak-b.json")), case.bars, case.signals)
    soak_ok = not first.halted and first.bars == second.bars == 10_000 and first.trades == second.trades and first.final_balance == second.final_balance and first.final_equity == second.final_equity and first.max_drawdown == second.max_drawdown
    checks.append(GateCheck("deterministic-soak", soak_ok, f"bars={first.bars}, trades={first.trades}, drawdown={first.max_drawdown:.4f}, halted={first.halted}"))

    with tempfile.TemporaryDirectory(prefix="aria-parity-gate-") as temp:
        certificate = certify_three_way_parity(candles=candles, symbol="EURUSD", timeframe="5m", checkpoint_path=Path(temp) / "parity.json", start_index=100)
    parity_ok = certificate.passed
    detail = f"candles={certificate.candles}, compared={certificate.compared}, mismatches={len(certificate.mismatches)}, paper_trades={certificate.paper_trades}, fingerprints={certificate.backtest_fingerprint[:12]}={certificate.realtime_fingerprint[:12]}={certificate.paper_fingerprint[:12]}"
    checks.append(GateCheck("three-way-parity", parity_ok, detail if parity_ok else detail + " :: " + " | ".join(certificate.mismatches[:3])))

    crash_ok, crash_detail = _process_crash_restart_check()
    checks.append(GateCheck("process-crash-restart", crash_ok, crash_detail))

    try:
        with tempfile.TemporaryDirectory(prefix="aria-shadow-gate-") as temp:
            shadow = run_long_shadow(historical_csv, checkpoint_dir=temp, max_rows=10_000)
        checks.append(GateCheck("real-history-shadow", shadow.passed, f"bars={shadow.bars}, compared={shadow.compared}, trades={shadow.paper_trades}, equity={shadow.paper_equity:.4f}, drawdown={shadow.paper_drawdown:.4f}, repeatable={shadow.repeatable}"))
    except Exception as exc:
        checks.append(GateCheck("real-history-shadow", False, str(exc)))

    checks.append(GateCheck("release-interpretation", all(check.passed for check in checks), "PASS means engineering/research gates passed; it does not imply profitability, future performance, or authorization for real-money execution"))
    return ReleaseGateReport(all(check.passed for check in checks), tuple(checks))


__all__ = ["GateCheck", "ReleaseGateReport", "run_release_gate"]
