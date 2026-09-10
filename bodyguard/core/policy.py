"""Bodyguard(Aria) policy helpers — Python research and server side (v0.05.0)."""

from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "bodyguard.config.json"
_PROBE_RE = re.compile(
    r"(\.\.|%2e%2e|/etc/passwd|<script|javascript:|union\s+select|drop\s+table|\{\{|\$\{|\bexec\b|\bxp_cmdshell\b|0x[0-9a-f]+)",
    re.I,
)
_FORBIDDEN_PROP_RE = re.compile(r"(__proto__|constructor|prototype|\$where)", re.I)


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


def normalize_and_detect_evasion(text: str) -> PolicyDecision:
    """Detect double encoding, null bytes, and traversal tricks."""
    if not text:
        return PolicyDecision(True, "ok", "R12")

    # Check for null bytes
    if "\x00" in text or "%00" in text.lower():
        return PolicyDecision(False, "null_byte_detected", "R12")

    # Test double URL-decoding
    decoded_once = urllib.parse.unquote(text)
    decoded_twice = urllib.parse.unquote(decoded_once)
    if decoded_once != decoded_twice and (".." in decoded_twice or "/" in decoded_twice):
        return PolicyDecision(False, "double_encoding_evasion_blocked", "R12")

    return PolicyDecision(True, "ok", "R12")


def detect_probe(text: str) -> PolicyDecision:
    if not text:
        return PolicyDecision(True, "ok", "R12")

    evasion = normalize_and_detect_evasion(text)
    if not evasion.allow:
        return evasion

    decoded = urllib.parse.unquote(text)
    if _PROBE_RE.search(text) or _PROBE_RE.search(decoded):
        return PolicyDecision(False, "probe_pattern_blocked", "R12")
    if any(ord(ch) < 32 for ch in text):
        return PolicyDecision(False, "control_chars", "R12")

    return PolicyDecision(True, "ok", "R12")


def detect_prototype_pollution(data: Any, max_depth: int = 5, current_depth: int = 1) -> PolicyDecision:
    """Enforce Rule R15: Prevent prototype pollution and deep recursion in payloads."""
    if current_depth > max_depth:
        return PolicyDecision(False, f"payload exceeds max depth ({max_depth})", "R15")

    if isinstance(data, dict):
        for key, val in data.items():
            if _FORBIDDEN_PROP_RE.search(str(key)):
                return PolicyDecision(False, f"prototype pollution key blocked: {key}", "R15", {"key": str(key)})
            res = detect_prototype_pollution(val, max_depth, current_depth + 1)
            if not res.allow:
                return res
    elif isinstance(data, list):
        for item in data:
            res = detect_prototype_pollution(item, max_depth, current_depth + 1)
            if not res.allow:
                return res

    return PolicyDecision(True, "ok", "R15")


def validate_execution_isolation(path: str, config: dict[str, Any] | None = None) -> PolicyDecision:
    """Enforce Rule R16: Reject execution/trading paths on public boundaries."""
    cfg = config or load_config()
    forbidden = cfg.get("api", {}).get("forbiddenExecutionPaths", [
        "/api/order", "/api/execute", "/api/trade", "/api/buy", "/api/sell", "/api/mt5"
    ])
    clean_path = path.split("?")[0].lower()
    for forbidden_path in forbidden:
        if clean_path.startswith(forbidden_path.lower()):
            return PolicyDecision(False, f"execution path forbidden: {forbidden_path}", "R16", {"path": path})
    return PolicyDecision(True, "ok", "R16")


def validate_cors_origin(origin: str, config: dict[str, Any] | None = None) -> PolicyDecision:
    """Enforce Rule R17: Strict origin allowlist check."""
    if not origin:
        return PolicyDecision(True, "same-origin", "R17")

    cfg = config or load_config()
    allowed = set(cfg.get("cors", {}).get("allowedOrigins", []))
    if origin.rstrip("/") not in {o.rstrip("/") for o in allowed}:
        return PolicyDecision(False, f"origin not allowed: {origin}", "R17", {"origin": origin})

    return PolicyDecision(True, "ok", "R17")


def reject_secret_shaped_client_payload(payload: dict[str, Any], config: dict[str, Any] | None = None) -> PolicyDecision:
    cfg = config or load_config()
    forbidden = [s.lower() for s in cfg.get("privacy", {}).get("forbidClientSecretNames", [])]
    blob = json.dumps(payload, ensure_ascii=True).lower()
    for name in forbidden:
        if name.lower() in blob:
            return PolicyDecision(False, "secret-shaped material in client payload", "R1", {"key": name})
    return PolicyDecision(True, "ok", "R1")
