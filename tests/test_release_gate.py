import pytest

from live.release_gate import evaluate_readiness, require_live_readiness


def test_readiness_blocks_when_any_item_is_missing():
    evidence = {item: True for item in range(1, 50)}
    decision = evaluate_readiness(evidence)
    assert not decision.ready
    assert decision.missing == (50,)


def test_readiness_passes_only_when_all_50_are_explicitly_true():
    evidence = {item: True for item in range(1, 51)}
    decision = evaluate_readiness(evidence)
    assert decision.ready
    assert decision.missing == ()
    require_live_readiness(evidence)


def test_readiness_rejects_false_and_missing_evidence():
    evidence = {1: True, 2: False, 4: True}
    with pytest.raises(RuntimeError, match="missing="):
        require_live_readiness(evidence)
