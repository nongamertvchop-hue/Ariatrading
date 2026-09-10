"""Fail-closed cross-language security/data-integrity verification gate.

This gate never executes broker actions. It feeds adversarial OHLC records to
independent native validators and requires every configured validator to reject
malformed input before the evidence is accepted.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Validator:
    name: str
    command: tuple[str, ...]


CASES = (
    ("valid", "1725900000\t1.1000\t1.1020\t1.0990\t1.1010"),
    ("valid", "1725900060\t1.1010\t1.1030\t1.1000\t1.1020"),
    ("bad_geometry", "1725900120\t1.1020\t1.1000\t1.1010\t1.0990"),
    ("bad_time", "1725900060\t1.1020\t1.1030\t1.1000\t1.1020"),
    ("bad_nan", "1725900180\tNaN\t1.1030\t1.1000\t1.1020"),
    ("bad_volume", "1725900240\t1.1020\t1.1040\t1.1010\t1.1030\t-1"),
)


def _run(validator: Validator, rows: str, timeout: float = 3.0) -> list[dict]:
    try:
        proc = subprocess.run(
            validator.command,
            input=rows,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            cwd=ROOT,
            env={"PATH": os.environ.get("PATH", ""), "LC_ALL": "C", "LANG": "C"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"{validator.name}: unavailable or timed out: {type(exc).__name__}") from exc
    if proc.returncode != 0:
        raise RuntimeError(f"{validator.name}: exit={proc.returncode}: {proc.stderr[-1000:]}")
    try:
        records = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{validator.name}: non-JSON output") from exc
    if len(records) != len(CASES):
        raise RuntimeError(f"{validator.name}: expected {len(CASES)} records, got {len(records)}")
    return records


def verify(validators: Sequence[Validator]) -> dict:
    if not validators:
        raise RuntimeError("security gate requires at least one validator")
    if len(validators) < 4:
        raise RuntimeError("security gate requires four independent validators")

    rows = "".join(row + "\n" for _, row in CASES)
    evidence: dict[str, list[dict]] = {}
    for validator in validators:
        evidence[validator.name] = _run(validator, rows)

    for name, records in evidence.items():
        for index, (case, _) in enumerate(CASES):
            ok = bool(records[index].get("ok"))
            if case == "valid" and not ok:
                raise RuntimeError(f"{name}: rejected known-valid case {index}")
            if case != "valid" and ok:
                raise RuntimeError(f"{name}: accepted adversarial case {index} ({case})")

    return {
        "ok": True,
        "validators": sorted(evidence),
        "required_agreement": len(validators),
        "cases": len(CASES),
        "security_properties": [
            "finite_positive_prices",
            "ohlc_geometry",
            "strict_timestamp_order",
            "non_negative_volume",
            "independent_cross_language_agreement",
            "fail_closed_on_missing_or_malformed_worker",
        ],
    }


def validators_from_environment() -> list[Validator]:
    raw = os.environ.get("ARIATRADING_SECURITY_WORKERS", "")
    if not raw:
        return []
    config = json.loads(raw)
    if not isinstance(config, dict):
        raise RuntimeError("ARIATRADING_SECURITY_WORKERS must be a JSON object")
    result: list[Validator] = []
    for name, command in config.items():
        if not isinstance(name, str) or not isinstance(command, list) or not all(isinstance(x, str) for x in command):
            raise RuntimeError("worker configuration must map names to string command arrays")
        result.append(Validator(name, tuple(command)))
    return result


if __name__ == "__main__":
    report = verify(validators_from_environment())
    print(json.dumps(report, indent=2, sort_keys=True))
