import json

import pytest

from live.state_store import JsonRuntimeStateStore


def test_state_store_round_trips_json(tmp_path):
    path = tmp_path / "nested" / "runtime.json"
    store = JsonRuntimeStateStore(path)
    state = {"version": 1, "session": {"balance": 1000.0, "pending": False}}

    store.save(state)

    assert store.exists()
    assert store.load() == state


def test_state_store_replaces_previous_checkpoint_atomically(tmp_path):
    store = JsonRuntimeStateStore(tmp_path / "runtime.json")
    store.save({"version": 1, "sequence": 1})
    store.save({"version": 1, "sequence": 2})

    assert store.load()["sequence"] == 2
    assert not list(tmp_path.glob("*.tmp"))
    assert not list(tmp_path.glob(".runtime.json.*.tmp"))


def test_state_store_rejects_non_object_json(tmp_path):
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    store = JsonRuntimeStateStore(path)

    with pytest.raises(ValueError, match="checkpoint root must be a dictionary"):
        store.load()


def test_state_store_reports_corrupt_json(tmp_path):
    path = tmp_path / "runtime.json"
    path.write_text("{broken", encoding="utf-8")
    store = JsonRuntimeStateStore(path)

    with pytest.raises(RuntimeError, match="failed to load runtime checkpoint"):
        store.load()
