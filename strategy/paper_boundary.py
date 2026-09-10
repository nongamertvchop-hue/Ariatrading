"""Static safety boundary for the paper/demo runtime.

The project contains isolated live-execution research code under ``live/``.
The 0.16 paper release must prove that the paper strategy/runtime path does not
import or call that execution surface.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SELF = Path(__file__).resolve()

# Keep this list deliberately small and high-confidence. Generic words such as
# ``order`` or ``broker`` are valid concepts in a paper simulator.
FORBIDDEN_REFERENCES = (
    "from live",
    "import live",
    "MT5LiveExecutor",
    "MetaTrader5",
    "ccxt",
    "order_send",
    "send_order",
    "place_order",
    "create_order",
)


def _python_files() -> list[Path]:
    files: list[Path] = []
    strategy_root = ROOT / "strategy"
    files.extend(sorted(strategy_root.glob("*.py")))
    files.append(ROOT / "adapters" / "paper_broker.py")
    files.append(ROOT / "scripts" / "run_paper_runtime.py")
    # The scanner contains the forbidden vocabulary as policy data, so it must
    # not report its own rule table as an application-level violation.
    return [path for path in files if path.exists() and path.resolve() != _SELF]


def verify_paper_boundary() -> tuple[bool, tuple[str, ...]]:
    findings: list[str] = []
    for path in _python_files():
        try:
            text = path.read_text(encoding="utf-8")
            ast.parse(text, filename=str(path))
        except (OSError, SyntaxError) as exc:
            findings.append(f"{path}: cannot parse paper path ({exc})")
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for forbidden in FORBIDDEN_REFERENCES:
                if forbidden in line:
                    findings.append(f"{path}:{line_number}: forbidden live execution reference: {forbidden}")
    return not findings, tuple(findings)


__all__ = ["verify_paper_boundary"]
