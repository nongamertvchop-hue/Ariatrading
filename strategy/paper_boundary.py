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

FORBIDDEN_IMPORT_MODULES = {"live", "MetaTrader5", "ccxt"}
FORBIDDEN_NAMES = {"MT5LiveExecutor", "MetaTrader5", "ccxt"}
FORBIDDEN_CALL_ATTRIBUTES = {"order_send", "send_order", "place_order", "create_order"}


def _python_files() -> list[Path]:
    files: list[Path] = []
    strategy_root = ROOT / "strategy"
    files.extend(sorted(strategy_root.glob("*.py")))
    files.append(ROOT / "adapters" / "paper_broker.py")
    files.append(ROOT / "scripts" / "run_paper_runtime.py")
    return [path for path in files if path.exists() and path.resolve() != _SELF]


def _module_is_forbidden(module: str | None) -> bool:
    if not module:
        return False
    root = module.split(".", 1)[0]
    return root in FORBIDDEN_IMPORT_MODULES


def verify_paper_boundary() -> tuple[bool, tuple[str, ...]]:
    findings: list[str] = []
    for path in _python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as exc:
            findings.append(f"{path}: cannot parse paper path ({exc})")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _module_is_forbidden(alias.name):
                        findings.append(f"{path}:{node.lineno}: forbidden live import: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if _module_is_forbidden(node.module):
                    findings.append(f"{path}:{node.lineno}: forbidden live import: {node.module}")
            elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
                findings.append(f"{path}:{node.lineno}: forbidden live symbol: {node.id}")
            elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_CALL_ATTRIBUTES:
                findings.append(f"{path}:{node.lineno}: forbidden broker call: {node.attr}")

    return not findings, tuple(findings)


__all__ = ["verify_paper_boundary"]
