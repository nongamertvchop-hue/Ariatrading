"""Inventory actual language usage instead of trusting the registry alone."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "polyglot" / "languages.json"

EXTENSIONS = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".cpp": "C++", ".cc": "C++",
    ".c": "C", ".go": "Go", ".java": "Java", ".rs": "Rust", ".cs": "C#", ".rb": "Ruby",
    ".php": "PHP", ".swift": "Swift", ".kt": "Kotlin", ".scala": "Scala", ".r": "R",
    ".sql": "SQL", ".sh": "Bash", ".ps1": "PowerShell", ".lua": "Lua", ".jl": "Julia",
}
TOOLCHAINS = {"Python": "python", "JavaScript": "node", "TypeScript": "tsc", "C++": "g++", "C": "gcc", "Go": "go", "Java": "javac", "Rust": "rustc"}


def inventory() -> dict:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    found: dict[str, list[str]] = {}
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in {".git", "node_modules", ".venv", "venv"} for part in path.parts):
            continue
        language = EXTENSIONS.get(path.suffix.lower())
        if language:
            found.setdefault(language, []).append(str(path.relative_to(ROOT)))

    operational = {}
    for language, files in sorted(found.items()):
        compiler = TOOLCHAINS.get(language)
        operational[language] = {
            "source_files": len(files),
            "toolchain": compiler,
            "toolchain_present": bool(shutil.which(compiler)) if compiler else None,
            "sample_files": files[:8],
        }

    registry_names = {entry["name"] for entry in registry["languages"]}
    return {
        "registry_count": len(registry_names),
        "source_detected_count": len(found),
        "operational": operational,
        "registry_only": sorted(registry_names - set(found)),
    }


if __name__ == "__main__":
    print(json.dumps(inventory(), indent=2, sort_keys=True))
