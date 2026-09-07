import pytest

from strategy.research_provenance import (
    PROVENANCE_SCHEMA_VERSION,
    ResearchProvenance,
    build_research_provenance,
    fingerprint_payload,
    provenance_compatible,
)


def test_fingerprint_is_deterministic_for_mapping_order():
    assert fingerprint_payload({"b": 2, "a": 1}) == fingerprint_payload({"a": 1, "b": 2})


def test_nan_payload_is_rejected():
    with pytest.raises(ValueError, match="finite"):
        fingerprint_payload(float("nan"))


def test_provenance_is_stable_for_identical_inputs():
    kwargs = dict(
        dataset=[{"time": "2026-01-01T00:00:00Z", "close": 1.1}],
        feature_names=["direction", "setup_score"],
        model_name="hgb",
        model_config={"max_depth": 3, "learning_rate": 0.05},
        code_version="0.13.2",
    )
    left = build_research_provenance(**kwargs)
    right = build_research_provenance(**kwargs)
    assert left == right
    assert left.fingerprint == right.fingerprint


def test_feature_order_changes_provenance():
    base = dict(
        dataset=[1, 2, 3],
        model_name="transformer",
        model_config={"hidden_size": 32},
        code_version="0.13.2",
    )
    left = build_research_provenance(feature_names=["a", "b"], **base)
    right = build_research_provenance(feature_names=["b", "a"], **base)
    assert left.feature_fingerprint != right.feature_fingerprint
    assert not provenance_compatible(left, right)


def test_model_config_change_breaks_compatibility():
    base = dict(
        dataset=[1, 2, 3],
        feature_names=["a", "b"],
        model_name="lstm",
        code_version="0.13.2",
    )
    left = build_research_provenance(model_config={"hidden_size": 32}, **base)
    right = build_research_provenance(model_config={"hidden_size": 64}, **base)
    assert not provenance_compatible(left, right)


def test_provenance_record_validates_schema():
    with pytest.raises(ValueError, match="schema"):
        ResearchProvenance("d", "f", "m", "c", "v", PROVENANCE_SCHEMA_VERSION + 1)
