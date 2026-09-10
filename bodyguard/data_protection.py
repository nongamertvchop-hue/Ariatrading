"""Data-loss prevention helpers for Bodyguard(Aria).

This module is intentionally dependency-free and side-effect free. It is used to
sanitize logs and public payloads before untrusted data can cross a boundary.
It does not attempt to be a perfect secret detector; callers should still keep
real secrets out of source control and client-side code.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

REDACTED = "[REDACTED]"

_SENSITIVE_KEY_RE = re.compile(
    r"(?:^|[_-])(api[_-]?key|access[_-]?token|auth(?:orization)?|bearer|password|passwd|secret|private[_-]?key|client[_-]?secret|refresh[_-]?token|session[_-]?token|cookie|set[_-]?cookie)(?:$|[_-])",
    re.IGNORECASE,
)

_SECRET_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE),
    re.compile(r"\b(?:sk|pk)_[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
)


def _redact_string(value: str) -> str:
    result = value
    for pattern in _SECRET_VALUE_PATTERNS:
        result = pattern.sub(REDACTED, result)
    return result


def sanitize_for_boundary(value: Any, *, max_depth: int = 8, max_items: int = 200) -> Any:
    """Return a bounded copy with sensitive keys/values redacted.

    Unknown objects are converted to a short string rather than serialized
    through arbitrary object hooks. This avoids accidentally invoking custom
    serialization code at a security boundary.
    """

    def visit(item: Any, depth: int) -> Any:
        if depth > max_depth:
            return REDACTED
        if item is None or isinstance(item, (bool, int, float)):
            return item
        if isinstance(item, str):
            return _redact_string(item)
        if isinstance(item, Mapping):
            result: dict[str, Any] = {}
            for index, (key, child) in enumerate(item.items()):
                if index >= max_items:
                    result["[TRUNCATED]"] = REDACTED
                    break
                safe_key = str(key)
                result[safe_key] = REDACTED if _SENSITIVE_KEY_RE.search(safe_key) else visit(child, depth + 1)
            return result
        if isinstance(item, Sequence) and not isinstance(item, (bytes, bytearray)):
            return [visit(child, depth + 1) for child in item[:max_items]]
        return _redact_string(str(item))

    return visit(value, 0)


def sanitize_log_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Sanitize a structured log record before it is emitted or persisted."""

    sanitized = sanitize_for_boundary(record)
    if not isinstance(sanitized, dict):
        raise TypeError("log record must sanitize to a mapping")
    return sanitized


def sanitize_public_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Sanitize a mapping intended to cross into an untrusted client."""

    sanitized = sanitize_for_boundary(payload)
    if not isinstance(sanitized, dict):
        raise TypeError("public payload must sanitize to a mapping")
    return sanitized
