import json

from live.demo_control import DemoControlClient


class FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_control_client_reads_demo_only_state():
    calls = []

    def opener(request, timeout):
        calls.append((request.method, request.full_url, request.headers.get("Authorization")))
        return FakeResponse({
            "enabled": True,
            "mode": "DEMO_ONLY",
            "updatedAt": "2026-09-07T08:00:00Z",
            "updatedBy": "webaria-ui",
            "runtimeHeartbeatAt": "2026-09-07T08:00:01Z",
            "runtimeId": "runtime-1",
        })

    client = DemoControlClient("https://example.test", "secret", opener=opener)
    state = client.get_state()

    assert state.enabled is True
    assert state.mode == "DEMO_ONLY"
    assert calls == [("GET", "https://example.test/api/auto-trading", "Bearer secret")]


def test_control_client_toggle_and_heartbeat_use_authenticated_requests():
    calls = []

    def opener(request, timeout):
        calls.append((request.method, request.full_url, request.get_header("Authorization"), request.get_header("X-aria-runtime-id")))
        if request.full_url.endswith("/heartbeat"):
            return FakeResponse({"enabled": False, "mode": "DEMO_ONLY", "runtimeHeartbeatAt": "2026-09-07T08:00:03Z", "runtimeId": "runtime-1"})
        return FakeResponse({"enabled": True, "mode": "DEMO_ONLY", "updatedAt": "2026-09-07T08:00:02Z", "updatedBy": "test"})

    client = DemoControlClient("https://example.test", "secret", opener=opener)
    assert client.set_enabled(True).enabled is True
    assert client.heartbeat().runtime_id == "runtime-1"

    assert calls[0][0:3] == ("POST", "https://example.test/api/auto-trading", "Bearer secret")
    assert calls[1][0:3] == ("POST", "https://example.test/api/auto-trading/heartbeat", "Bearer secret")


def test_control_client_fails_closed_on_bad_mode():
    def opener(request, timeout):
        return FakeResponse({"enabled": True, "mode": "LIVE"})

    client = DemoControlClient("https://example.test", "secret", opener=opener)
    assert client.is_enabled() is False


def test_runtime_online_is_false_for_stale_heartbeat():
    def opener(request, timeout):
        return FakeResponse({
            "enabled": True,
            "mode": "DEMO_ONLY",
            "runtimeHeartbeatAt": "2020-01-01T00:00:00Z",
            "runtimeId": "runtime-1",
        })

    client = DemoControlClient("https://example.test", "secret", opener=opener)
    state = client.get_state()
    assert state.runtime_online is False
