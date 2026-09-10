import pytest

from live.release_evidence import EvidenceRecord, build_readiness_map, load_evidence, save_evidence


def test_evidence_requires_reference_and_valid_item():
    with pytest.raises(ValueError):
        EvidenceRecord.create(0, True, "demo-log")
    with pytest.raises(ValueError):
        EvidenceRecord.create(1, True, "")


def test_latest_evidence_wins(tmp_path):
    records = [EvidenceRecord.create(19, False, "run-a"), EvidenceRecord.create(19, True, "run-b")]
    assert build_readiness_map(records) == {19: True}
    path = tmp_path / "release_evidence.json"
    save_evidence(path, records)
    loaded = load_evidence(path)
    assert len(loaded) == 2
    assert build_readiness_map(loaded)[19] is True


def test_missing_evidence_stays_unproven(tmp_path):
    path = tmp_path / "missing.json"
    assert build_readiness_map(load_evidence(path)) == {}
