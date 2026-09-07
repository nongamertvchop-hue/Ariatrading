import json

import pytest

from strategy.execution_audit import AuditJournal, AuditJournalError


def test_audit_journal_appends_and_verifies_chain(tmp_path):
    journal = AuditJournal(tmp_path / "execution.jsonl")

    first = journal.append(
        event_id="e-1",
        event_type="ORDER_CREATED",
        client_order_id="c-1",
        state="CREATED",
        filled_quantity=0,
        reason="signal accepted",
    )
    second = journal.append(
        event_id="e-2",
        event_type="ORDER_FILLED",
        client_order_id="c-1",
        state="FILLED",
        broker_order_id="b-1",
        filled_quantity=1,
        reason="broker confirmed",
    )

    events = journal.verify()
    assert events == (first, second)
    assert second.previous_hash == first.event_hash


def test_audit_journal_detects_tampering(tmp_path):
    path = tmp_path / "execution.jsonl"
    journal = AuditJournal(path)
    journal.append(
        event_id="e-1",
        event_type="ORDER_CREATED",
        client_order_id="c-1",
        state="CREATED",
    )
    lines = path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[0])
    record["reason"] = "tampered"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(AuditJournalError):
        journal.verify()


def test_audit_journal_detects_chain_break(tmp_path):
    journal = AuditJournal(tmp_path / "execution.jsonl")
    journal.append(event_id="e-1", event_type="A", client_order_id="c-1", state="CREATED")
    journal.append(event_id="e-2", event_type="B", client_order_id="c-1", state="SUBMITTING")
    lines = (tmp_path / "execution.jsonl").read_text(encoding="utf-8").splitlines()
    second = json.loads(lines[1])
    second["previous_hash"] = "BROKEN"
    second["event_hash"] = __import__("hashlib").sha256(
        json.dumps(
            {key: value for key, value in second.items() if key != "event_hash"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    (tmp_path / "execution.jsonl").write_text(
        lines[0] + "\n" + json.dumps(second, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(AuditJournalError):
        journal.verify()


def test_empty_or_missing_journal_verifies_as_empty(tmp_path):
    assert AuditJournal(tmp_path / "missing.jsonl").verify() == ()
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    assert AuditJournal(path).verify() == ()


def test_invalid_append_arguments_are_rejected(tmp_path):
    journal = AuditJournal(tmp_path / "execution.jsonl")
    with pytest.raises(ValueError):
        journal.append(event_id="", event_type="A", client_order_id="c", state="CREATED")
    with pytest.raises(ValueError):
        journal.append(event_id="e", event_type="A", client_order_id="c", state="CREATED", filled_quantity=-1)
