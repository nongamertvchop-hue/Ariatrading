"""Run one or more external polyglot market-data validators safely.

This is intentionally a research/integration utility rather than part of the
hot strategy loop. External commands receive only canonical TSV OHLC rows and
must return JSONL records with ``ok: true`` for every input row.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class ValidatorResult:
    runtime: str
    accepted: int
    rejected: int
    output: tuple[dict, ...]


def encode_tsv(candles: Sequence[dict]) -> str:
    lines: list[str] = []
    for candle in candles:
        values = [
            int(candle["time"]),
            float(candle["open"]),
            float(candle["high"]),
            float(candle["low"]),
            float(candle["close"]),
        ]
        if "volume" in candle and candle["volume"] is not None:
            values.append(float(candle["volume"]))
        lines.append("\t".join(str(v) for v in values))
    return "\n".join(lines) + ("\n" if lines else "")


def run_validator(runtime: str, command: Sequence[str], candles: Sequence[dict], timeout_s: float = 10.0) -> ValidatorResult:
    if not runtime.strip():
        raise ValueError("runtime must be non-empty")
    if not command:
        raise ValueError("command must be non-empty")
    payload = encode_tsv(candles).encode("utf-8")
    completed = subprocess.run(
        list(command),
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_s,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"{runtime} validator failed with exit code {completed.returncode}: {completed.stderr.decode('utf-8', 'replace').strip()}")
    records: list[dict] = []
    for line in completed.stdout.decode("utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{runtime} validator emitted invalid JSONL") from exc
        if not isinstance(value, dict) or not isinstance(value.get("ok"), bool):
            raise RuntimeError(f"{runtime} validator emitted an invalid protocol record")
        records.append(value)
    accepted = sum(1 for value in records if value["ok"])
    rejected = len(records) - accepted
    if len(records) != len([c for c in candles if c]):
        raise RuntimeError(f"{runtime} validator returned {len(records)} records for {len(candles)} candles")
    if rejected:
        raise ValueError(f"{runtime} rejected {rejected} candle(s)")
    return ValidatorResult(runtime, accepted, rejected, tuple(records))


__all__ = ["ValidatorResult", "encode_tsv", "run_validator"]
