import json

from live.telemetry import RuntimeTelemetry


def test_heartbeat_is_atomic_json(tmp_path):
    telemetry = RuntimeTelemetry(tmp_path / "heartbeat.json", tmp_path / "events.jsonl")
    telemetry.heartbeat(status="READY", mode="DEMO", account=123, processed=2)
    payload = json.loads((tmp_path / "heartbeat.json").read_text(encoding="utf-8"))
    assert payload["status"] == "READY"
    assert payload["mode"] == "DEMO"
    assert payload["account"] == 123
    assert payload["processed"] == 2


def test_event_log_is_jsonl(tmp_path):
    telemetry = RuntimeTelemetry(tmp_path / "heartbeat.json", tmp_path / "events.jsonl")
    telemetry.event("cycle_completed", account=123, processed=3)
    telemetry.event("spread_gate", symbol="EURUSD", spread_points=42.0)
    rows = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["event"] for row in rows] == ["cycle_completed", "spread_gate"]
    assert rows[1]["spread_points"] == 42.0
