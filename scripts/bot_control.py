"""Operator control CLI for the Ariatrading runtime."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from live.control_plane import BotControlPlane, EMERGENCY_STOP, PAUSE, RUN, STOP

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "data" / "bot_control.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Ariatrading bot control")
    parser.add_argument(
        "command", choices=["status", "start", "pause", "stop", "emergency-stop"]
    )
    parser.add_argument("--reason", default="operator request")
    args = parser.parse_args()
    control = BotControlPlane(STATE_FILE)

    if args.command == "status":
        print(json.dumps(control.read().__dict__, indent=2, sort_keys=True))
        return 0

    state = {
        "start": RUN,
        "pause": PAUSE,
        "stop": STOP,
        "emergency-stop": EMERGENCY_STOP,
    }[args.command]
    result = control.set(state, args.reason)
    print(json.dumps(result.__dict__, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
