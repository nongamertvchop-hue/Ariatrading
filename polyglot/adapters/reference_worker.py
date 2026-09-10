#!/usr/bin/env python3
"""Reference Polyglot worker used for contract tests and local development."""
from __future__ import annotations

import json
import math
import sys
from typing import Any


def main() -> int:
    line = sys.stdin.readline()
    if not line:
        return 2
    try:
        request = json.loads(line)
    except json.JSONDecodeError:
        return 3

    payload: dict[str, Any] = request.get("payload", {})
    candles = payload.get("candles", [])
    finite = True
    previous_time = None
    for candle in candles if isinstance(candles, list) else []:
        try:
            values = [float(candle[k]) for k in ("open", "high", "low", "close")]
            finite = finite and all(math.isfinite(value) for value in values)
            current_time = int(candle["time"])
            finite = finite and (previous_time is None or current_time > previous_time)
            previous_time = current_time
        except (KeyError, TypeError, ValueError, OverflowError):
            finite = False
            break

    response = {
        "schema_version": "1.0",
        "request_id": request.get("request_id"),
        "ok": bool(finite),
        "result": {
            "validator": "reference-python",
            "task": request.get("task"),
            "checks": {"ordered_finite_ohlc": bool(finite)},
        },
    }
    print(json.dumps(response, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
