"""Output and log sanitization helpers for Bodyguard(Aria) (v0.05.0)."""

from __future__ import annotations

import re
from typing import Any

_SECRET_VALUE = re.compile(r"(?i)(api[_-]?key|token|secret|password|mt5_pass(word)?)\s*[:=]\s*([^\n\r\s,;\"']{6,})")
_EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_TELEGRAM_BOT_TOKEN = re.compile(r"\b([0-9]{8,12}:[a-zA-Z0-9_-]{35})\b")
_JWT_TOKEN = re.compile(r"\beyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b")
_PRIVATE_KEY = re.compile(r"-----BEGIN[ A-Z_-]*PRIVATE KEY-----.*?-----END[ A-Z_-]*PRIVATE KEY-----", re.DOTALL)


def scrub_text(text: str) -> str:
    if not text:
        return text
    cleaned = _PRIVATE_KEY.sub("[REDACTED_PRIVATE_KEY]", text)
    cleaned = _SECRET_VALUE.sub(r"\1=[REDACTED]", cleaned)
    cleaned = _TELEGRAM_BOT_TOKEN.sub("[REDACTED_TELEGRAM_TOKEN]", cleaned)
    cleaned = _JWT_TOKEN.sub("[REDACTED_JWT]", cleaned)
    cleaned = _EMAIL.sub("[REDACTED_EMAIL]", cleaned)
    return cleaned


def scrub_mapping(data: dict[str, Any], redact_keys: list[str] | None = None) -> dict[str, Any]:
    default_keys = [
        "apikey",
        "api_key",
        "token",
        "secret",
        "password",
        "email",
        "phone",
        "telegram_bot_token",
        "chat_id",
        "mt5_password",
    ]
    keys = {k.lower() for k in (redact_keys or default_keys)}
    out: dict[str, Any] = {}
    for key, value in data.items():
        if key.lower() in keys:
            out[key] = "[REDACTED]"
        elif isinstance(value, dict):
            out[key] = scrub_mapping(value, redact_keys)
        elif isinstance(value, list):
            out[key] = [
                scrub_mapping(item, redact_keys) if isinstance(item, dict)
                else scrub_text(item) if isinstance(item, str)
                else item
                for item in value
            ]
        elif isinstance(value, str):
            out[key] = scrub_text(value)
        else:
            out[key] = value
    return out


def safe_public_error(message: str, code: str = "rejected") -> dict[str, str]:
    return {"error": code, "message": scrub_text(message)[:240]}
