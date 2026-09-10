"""Run external language workers through a strict JSONL boundary.

The runner is research/validation infrastructure only. It never sends broker
orders and it cannot promote a strategy decision to LIVE execution.

Worker contract:
  stdin:  one JSON request per line
  stdout: one JSON response per line
  exit:   0 on success; non-zero on worker failure

A worker should return at minimum:
  {"schema_version":"1.0","request_id":"...","ok":true,"result":{...}}
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


class PolyglotContractError(ValueError):
    """Raised when a worker violates the Ariatrading protocol."""


@dataclass(frozen=True)
class WorkerSpec:
    name: str
    command: tuple[str, ...]
    timeout_seconds: float = 5.0


@dataclass(frozen=True)
class WorkerResult:
    worker: str
    ok: bool
    response: dict[str, Any]
    stderr: str = ""


def _validate_response(request_id: str, response: Any) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise PolyglotContractError("worker response must be an object")
    if response.get("schema_version") != "1.0":
        raise PolyglotContractError("unsupported worker schema_version")
    if response.get("request_id") != request_id:
        raise PolyglotContractError("request_id mismatch")
    if not isinstance(response.get("ok"), bool):
        raise PolyglotContractError("worker response 'ok' must be boolean")
    if not isinstance(response.get("result", {}), dict):
        raise PolyglotContractError("worker response 'result' must be object")
    return response


def run_worker(spec: WorkerSpec, request: dict[str, Any]) -> WorkerResult:
    """Execute one worker with bounded resources and fail-closed parsing."""
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        raise PolyglotContractError("request_id is required")

    env = {
        "PATH": os.environ.get("PATH", ""),
        "LC_ALL": "C",
        "LANG": "C",
    }

    try:
        completed = subprocess.run(
            list(spec.command),
            input=json.dumps(request, separators=(",", ":"), ensure_ascii=True) + "\n",
            text=True,
            capture_output=True,
            timeout=spec.timeout_seconds,
            check=False,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return WorkerResult(
            worker=spec.name,
            ok=False,
            response={
                "schema_version": "1.0",
                "request_id": request_id,
                "ok": False,
                "result": {"error": type(exc).__name__, "message": str(exc)},
            },
            stderr=str(exc),
        )

    if completed.returncode != 0:
        return WorkerResult(
            worker=spec.name,
            ok=False,
            response={
                "schema_version": "1.0",
                "request_id": request_id,
                "ok": False,
                "result": {"error": "worker_exit", "returncode": completed.returncode},
            },
            stderr=completed.stderr[-4000:],
        )

    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        return WorkerResult(
            worker=spec.name,
            ok=False,
            response={
                "schema_version": "1.0",
                "request_id": request_id,
                "ok": False,
                "result": {"error": "protocol", "message": "worker must emit exactly one JSON line"},
            },
            stderr=completed.stderr[-4000:],
        )

    try:
        raw = json.loads(lines[0])
        response = _validate_response(request_id, raw)
    except (json.JSONDecodeError, PolyglotContractError) as exc:
        return WorkerResult(
            worker=spec.name,
            ok=False,
            response={
                "schema_version": "1.0",
                "request_id": request_id,
                "ok": False,
                "result": {"error": "protocol", "message": str(exc)},
            },
            stderr=completed.stderr[-4000:],
        )

    return WorkerResult(spec.name, bool(response["ok"]), response, completed.stderr[-4000:])


def run_consensus(
    workers: Sequence[WorkerSpec], request: dict[str, Any], *, min_agree: int = 2
) -> tuple[bool, list[WorkerResult]]:
    """Require enough independent validators to agree.

    Consensus is *validation*, never signal creation. Missing/unavailable workers
    are not counted as agreement, and zero valid workers always fails closed.
    """
    if not workers:
        return False, []
    if min_agree < 1 or min_agree > len(workers):
        raise ValueError("min_agree must be between 1 and worker count")

    results = [run_worker(worker, request) for worker in workers]
    valid = [result for result in results if result.ok]
    return len(valid) >= min_agree, results


if __name__ == "__main__":
    # Small smoke-run utility: `python -m polyglot.runner command...`
    command = tuple(sys.argv[1:])
    if not command:
        raise SystemExit("usage: python -m polyglot.runner <worker-command>")
    request = {
        "schema_version": "1.0",
        "request_id": "smoke-0001",
        "task": "validate_market_snapshot",
        "payload": {"source": "polyglot-smoke"},
    }
    result = run_worker(WorkerSpec("cli", command), request)
    print(json.dumps(result.response, indent=2, sort_keys=True))
    raise SystemExit(0 if result.ok else 1)
