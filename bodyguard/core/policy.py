"""Bodyguard(Aria) policy helpers — Python research side.

Defensive evaluation only. No network calls, no offensive behavior.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "bodyguard.config.json"
_SYMBOL_RE = re.compile(r"^[A-Z]{3}/[A-Z]{3}$")


@dataclass(frozen=True)
class PolicyDecision:
    allow: bool
    reason: str
    rule: str
    meta: dict[str, Any] | None = None


def load_config(path: Path | None = None) -> dict[str, Any]:
    target = path or _CONFIG_PATH
    with target.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_symbol(symbol: str, config: dict[str, Any] | None = None) -> PolicyDecision:
    cfg = config or load_config()
    pattern = cfg.get("api", {}).get("symbolPattern") or "^[A-Z]{3}/[A-Z]{3}$"
    if not isinstance(symbol, str) or not symbol:
        return PolicyDecision(False, "symbol missing", "R4")
    if len(symbol) > 16:
        return PolicyDecision(False, "symbol too long", "R4")
    if not re.match(pattern, symbol.upper()):
        return PolicyDecision(False, "symbol format rejected", "R4")
    return PolicyDecision(True, "ok", "R4")


def validate_timeframe(timeframe: str, config: dict[str, Any] | None = None) -> PolicyDecision:
    cfg = config or load_config()
    allowed = set(cfg.get("api", {}).get("allowedTimeframes") or [])
    if timeframe not in allowed:
        return PolicyDecision(False, f"timeframe not allowed: {timeframe}", "R4")
    return PolicyDecision(True, "ok", "R4")


def validate_method(method: str, config: dict[str, Any] | None = None) -> PolicyDecision:
    cfg = config or load_config()
    allowed = {m.upper() for m in cfg.get("http", {}).get("allowedMethods", ["GET"])}
    if method.upper() not in allowed:
        return PolicyDecision(False, f"method not allowed: {method}", "R3")
    return PolicyDecision(True, "ok", "R3")


def reject_secret_shaped_client_payload(payload: dict[str, Any], config: dict[str, Any] | None = None) -> PolicyDecision:
    """Block obvious attempts to push secrets through client-facing structures."""
    cfg = config or load_config()
    forbidden = [s.lower() for s in cfg.get("privacy", {}).get("forbidClientSecretNames", [])]
    blob = json.dumps(payload, ensure_ascii=True).lower()
    for name in forbidden:
        if name.lower() in blob:
            return PolicyDecision(False, "secret-shaped material in client payload", "R1", {"key": name})
    return PolicyDecision(True, "ok", "R1")
