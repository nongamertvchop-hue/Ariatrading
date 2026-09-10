"""Minimal Python entrypoint for the canonical market-data validator."""

from __future__ import annotations

import json
import sys

from interop.python.adapter import validate_candle


def main() -> int:
    for index, line in enumerate(sys.stdin):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            candle = validate_candle(record)
            print(json.dumps({"ok": True, "index": index, "time": candle.time, "open": candle.open, "high": candle.high, "low": candle.low, "close": candle.close}, separators=(",", ":")))
        except (json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
            print(json.dumps({"ok": False, "index": index, "error": str(exc)}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
