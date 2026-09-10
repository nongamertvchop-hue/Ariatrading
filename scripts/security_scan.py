"""High-confidence repository secret scanner for Bodyguard CI.

This is intentionally conservative: it reports credential-shaped values, not
ordinary variable names such as ``api_key``. The goal is to fail the build when
an actual secret is accidentally committed to tracked files.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PATTERNS = (
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}")),
    ("provider_secret_assignment", re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password|private[_-]?key|refresh[_-]?token)\b\s*[:=]\s*[\"'][^\"']{20,}[\"']"
    )),
)

SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2", ".ttf", ".zip", ".pdf"}
SKIP_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__"}


def tracked_files() -> list[Path]:
    output = subprocess.check_output(["git", "ls-files", "-z"], text=False)
    return [Path(raw) for raw in output.split(b"\0") if raw]


def looks_like_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(token in lowered for token in ("redacted", "example", "placeholder", "dummy", "changeme"))


def scan_file(path: Path) -> list[str]:
    if path.suffix.lower() in SKIP_SUFFIXES or any(part in SKIP_PARTS for part in path.parts):
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    findings: list[str] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if looks_like_placeholder(line):
            continue
        for name, pattern in PATTERNS:
            if pattern.search(line):
                findings.append(f"{path}:{line_number}: {name}")
    return findings


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        findings.extend(scan_file(path))

    if findings:
        print("Bodyguard secret scan FAILED:")
        print("\n".join(findings))
        return 1

    print("Bodyguard secret scan passed: no high-confidence credential patterns found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
