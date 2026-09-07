"""Deterministic provenance fingerprints for reproducible ML/DL research.

The provenance layer records the exact logical inputs that define a research
run without depending on filesystem paths, wall-clock time, or object
addresses. It is descriptive metadata only: it does not train, select, or
promote a model.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


PROVENANCE_SCHEMA_VERSION = 1


def _canonical_json(value: Any) -> str:
    """Serialize JSON-compatible data deterministically."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def fingerprint_payload(value: Any) -> str:
    """Return a SHA-256 fingerprint of a canonical JSON-compatible payload."""
    try:
        serialized = _canonical_json(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("provenance payload must be finite and JSON serializable") from exc
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ResearchProvenance:
    """Immutable provenance record for one model/research artifact."""

    dataset_fingerprint: str
    feature_fingerprint: str
    model_name: str
    model_config_fingerprint: str
    code_version: str
    schema_version: int = PROVENANCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name, value in {
            "dataset_fingerprint": self.dataset_fingerprint,
            "feature_fingerprint": self.feature_fingerprint,
            "model_config_fingerprint": self.model_config_fingerprint,
            "code_version": self.code_version,
        }.items():
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.model_name, str) or not self.model_name:
            raise ValueError("model_name must be a non-empty string")
        if self.schema_version != PROVENANCE_SCHEMA_VERSION:
            raise ValueError("unsupported provenance schema version")

    @property
    def fingerprint(self) -> str:
        """Fingerprint the complete provenance record."""
        return fingerprint_payload(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "dataset_fingerprint": self.dataset_fingerprint,
            "feature_fingerprint": self.feature_fingerprint,
            "model_name": self.model_name,
            "model_config_fingerprint": self.model_config_fingerprint,
            "code_version": self.code_version,
        }


def build_research_provenance(
    *,
    dataset: Sequence[Any],
    feature_names: Sequence[str],
    model_name: str,
    model_config: Mapping[str, Any],
    code_version: str,
) -> ResearchProvenance:
    """Build provenance from logical experiment inputs.

    Dataset content is fingerprinted rather than its source path. Feature
    ordering is significant, because changing order changes model inputs even
    when the same feature names are present.
    """
    if not model_name:
        raise ValueError("model_name must not be empty")
    if not code_version:
        raise ValueError("code_version must not be empty")
    normalized_features = [str(name) for name in feature_names]
    if not normalized_features or any(not name for name in normalized_features):
        raise ValueError("feature_names must contain non-empty names")

    dataset_payload = list(dataset)
    model_payload = dict(model_config)
    dataset_fingerprint = fingerprint_payload(dataset_payload)
    feature_fingerprint = fingerprint_payload(normalized_features)
    model_config_fingerprint = fingerprint_payload(model_payload)

    return ResearchProvenance(
        dataset_fingerprint=dataset_fingerprint,
        feature_fingerprint=feature_fingerprint,
        model_name=model_name,
        model_config_fingerprint=model_config_fingerprint,
        code_version=code_version,
    )


def save_research_provenance(
    provenance: ResearchProvenance,
    path: str | os.PathLike[str],
) -> None:
    """Atomically persist provenance as canonical JSON."""
    if not isinstance(provenance, ResearchProvenance):
        raise TypeError("provenance must be a ResearchProvenance instance")

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    serialized = _canonical_json(provenance.to_dict())
    temporary = target.with_name(f".{target.name}.tmp")
    try:
        temporary.write_text(serialized, encoding="utf-8")
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise OSError(f"failed to persist research provenance: {exc}") from exc


def load_research_provenance(path: str | os.PathLike[str]) -> ResearchProvenance:
    """Load and validate a persisted provenance record."""
    target = Path(path)
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"failed to load research provenance: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("research provenance must be a JSON object")
    required = {
        "schema_version",
        "dataset_fingerprint",
        "feature_fingerprint",
        "model_name",
        "model_config_fingerprint",
        "code_version",
    }
    if set(raw) != required:
        raise ValueError("research provenance has an unexpected schema")
    try:
        return ResearchProvenance(
            dataset_fingerprint=str(raw["dataset_fingerprint"]),
            feature_fingerprint=str(raw["feature_fingerprint"]),
            model_name=str(raw["model_name"]),
            model_config_fingerprint=str(raw["model_config_fingerprint"]),
            code_version=str(raw["code_version"]),
            schema_version=int(raw["schema_version"]),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid research provenance fields") from exc


def provenance_compatible(left: ResearchProvenance, right: ResearchProvenance) -> bool:
    """Return whether two artifacts are comparable under strict provenance."""
    if not isinstance(left, ResearchProvenance) or not isinstance(right, ResearchProvenance):
        raise TypeError("both values must be ResearchProvenance instances")
    return (
        left.schema_version == right.schema_version
        and left.dataset_fingerprint == right.dataset_fingerprint
        and left.feature_fingerprint == right.feature_fingerprint
        and left.model_config_fingerprint == right.model_config_fingerprint
        and left.code_version == right.code_version
    )


__all__ = [
    "PROVENANCE_SCHEMA_VERSION",
    "ResearchProvenance",
    "build_research_provenance",
    "fingerprint_payload",
    "save_research_provenance",
    "load_research_provenance",
    "provenance_compatible",
]
