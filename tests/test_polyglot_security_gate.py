import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from polyglot.security_gate import Validator, verify  # noqa: E402
from polyglot.security_inventory import inventory  # noqa: E402


def test_inventory_detects_real_polyglot_sources():
    report = inventory()
    for language in ("Python", "JavaScript", "C++", "Go", "Java", "Rust"):
        assert language in report["operational"]
        assert report["operational"][language]["source_files"] > 0


def test_security_gate_requires_four_independent_validators():
    with pytest.raises(RuntimeError, match="four independent validators"):
        verify([Validator("only-one", ("true",))])


def test_security_manifest_is_valid_json():
    manifest = json.loads((ROOT / "polyglot" / "security_manifest.json").read_text())
    assert manifest["quorum"]["minimum_agreement"] == 4
    assert set(manifest["implemented_languages"]) >= {"Python", "JavaScript", "C++", "Go", "Java", "Rust"}
