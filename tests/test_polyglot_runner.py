from __future__ import annotations

import sys
from pathlib import Path

from polyglot.runner import WorkerSpec, run_consensus, run_worker


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "polyglot" / "adapters" / "reference_worker.py"


def _spec() -> WorkerSpec:
    return WorkerSpec("reference-python", (sys.executable, str(WORKER)), timeout_seconds=2.0)


def _request(candles):
    return {
        "schema_version": "1.0",
        "request_id": "test-123456",
        "task": "validate_market_snapshot",
        "payload": {"candles": candles},
    }


def test_reference_worker_accepts_ordered_finite_ohlc():
    result = run_worker(
        _spec(),
        _request(
            [
                {"time": 1, "open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15},
                {"time": 2, "open": 1.15, "high": 1.3, "low": 1.1, "close": 1.25},
            ]
        ),
    )
    assert result.ok is True
    assert result.response["result"]["checks"]["ordered_finite_ohlc"] is True


def test_reference_worker_rejects_non_finite_ohlc():
    result = run_worker(
        _spec(),
        _request([{"time": 1, "open": 1.1, "high": "NaN", "low": 1.0, "close": 1.15}]),
    )
    assert result.ok is False


def test_consensus_requires_agreement():
    ok, results = run_consensus([_spec(), _spec()], _request([]), min_agree=2)
    assert ok is True
    assert len(results) == 2


def test_consensus_fails_when_workers_are_unavailable():
    missing = WorkerSpec("missing", (str(ROOT / "does-not-exist"),), timeout_seconds=1.0)
    ok, results = run_consensus([missing], _request([]), min_agree=1)
    assert ok is False
    assert results[0].ok is False
