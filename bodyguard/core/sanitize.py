"""Output and log sanitization helpers for Bodyguard(Aria)."""

from __future__ import annotations

import re
from typing import Any

_SECRET_VALUE = re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*([^\n\r]{6,})")
_EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)


def scrub_text(text: str) -> str:
    if not text:
        return text
    cleaned = _SECRET_VALUE.sub(r"\1=[REDACTED]", text)
    cleaned = _EMAIL.sub("[REDACTED_EMAIL]", cleaned)
    return cleaned


def scrub_mapping(data: dict[str, Any], redact_keys: list[str] | None = None) -> dict[str, Any]:
    keys = {k.lower() for k in (redact_keys or ["apikey", "api_key", "token", "secret", "password", "email", "phone"])}
    out: dict[str, Any] = {}
    for key, value in data.items():
        if key.lower() in keys:
            out[key] = "[REDACTED]"
        elif isinstance(value, dict):
            out[key] = scrub_mapping(value, redact_keys)
        elif isinstance(value, str):
            out[key] = scrub_text(value)
        else:
            out[key] = value
    return out


def safe_public_error(message: str, code: str = "rejected") -> dict[str, str]:
    return {"error": code, "message": scrub_text(message)[:240]}
