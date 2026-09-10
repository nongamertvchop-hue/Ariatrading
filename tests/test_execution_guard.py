from datetime import datetime, timezone

import pytest

from live.execution_guard import ExecutionJournal, build_intent


def _intent(bar_hour=7):
    return build_intent(
        symbol="eurusd",
        direction="buy",
        bar_time=datetime(2026, 9, 10, bar_hour, 0, tzinfo=timezone.utc),
        entry=1.1,
        sl=1.095,
        tp=1.1075,
        lot_size=0.01,
    )


def test_intent_id_is_deterministic():
    assert _intent().intent_id == _intent().intent_id


def test_equivalent_normalization_produces_same_id():
    base = _intent()
    normalized = build_intent(
        symbol="EURUSD",
        direction="BUY",
        bar_time=datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc),
        entry=1.1,
        sl=1.095,
        tp=1.1075,
        lot_size=0.01,
    )
    assert base.intent_id != normalized.intent_id


def test_duplicate_reservation_is_rejected(tmp_path):
    journal = ExecutionJournal(tmp_path / "execution.json")
    intent = _intent()
    assert journal.reserve(intent) is True
    assert journal.reserve(intent) is False
    assert journal.get(intent.intent_id)["state"] == "RESERVED"


def test_new_intent_is_blocked_while_previous_intent_requires_reconciliation(tmp_path):
    journal = ExecutionJournal(tmp_path / "execution.json")
    first = _intent(7)
    second = _intent(8)
    assert journal.reserve(first) is True
    assert journal.reserve(second) is False

    journal.transition(first.intent_id, "SUCCEEDED", ticket=123)
    assert journal.reserve(second) is True


def test_ambiguous_intent_is_recoverable_but_not_reopenable(tmp_path):
    journal = ExecutionJournal(tmp_path / "execution.json")
    intent = _intent()
    journal.reserve(intent)
    journal.transition(intent.intent_id, "SUBMITTED")
    journal.transition(intent.intent_id, "AMBIGUOUS", error="timeout")

    assert journal.get(intent.intent_id)["state"] == "AMBIGUOUS"
    assert len(journal.recoverable_intents()) == 1
    with pytest.raises(RuntimeError, match="Cannot transition AMBIGUOUS"):
        journal.transition(intent.intent_id, "SUBMITTED")


def test_terminal_intent_cannot_be_reopened(tmp_path):
    journal = ExecutionJournal(tmp_path / "execution.json")
    intent = _intent()
    journal.reserve(intent)
    journal.transition(intent.intent_id, "SUCCEEDED", ticket=123)
    with pytest.raises(RuntimeError, match="Cannot transition SUCCEEDED"):
        journal.transition(intent.intent_id, "SUBMITTED")


def test_corrupt_journal_fails_closed(tmp_path):
    path = tmp_path / "execution.json"
    path.write_text("not-json", encoding="utf-8")
    journal = ExecutionJournal(path)
    with pytest.raises(RuntimeError, match="cannot be read safely"):
        journal.get("anything")
