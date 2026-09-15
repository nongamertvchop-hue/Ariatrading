from live.runtime_status import RuntimeStatusStore


def test_runtime_status_is_atomic_and_readable(tmp_path):
    path = tmp_path / "status.json"
    store = RuntimeStatusStore(path)

    store.write(runtime_state="RUNNING", mode="DEMO", processed=2)
    result = store.read()

    assert result["runtime_state"] == "RUNNING"
    assert result["mode"] == "DEMO"
    assert result["processed"] == 2
    assert result["updated_at"]


def test_missing_runtime_status_is_empty(tmp_path):
    assert RuntimeStatusStore(tmp_path / "missing.json").read() == {}


def test_invalid_runtime_status_fails_closed(tmp_path):
    path = tmp_path / "status.json"
    path.write_text("[]", encoding="utf-8")
    try:
        RuntimeStatusStore(path).read()
    except RuntimeError as exc:
        assert "must be an object" in str(exc)
    else:
        raise AssertionError("invalid runtime status was accepted")
