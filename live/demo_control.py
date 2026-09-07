"""Remote ON/OFF control client for the MT5 demo runtime.

The control plane is intentionally fail-closed: if the control endpoint is
unreachable, malformed, unauthorized, or reports a non-demo mode, callers
must treat automatic entry as disabled.
"""

from __future__ import annotations

import json
import secrets
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any


class DemoControlError(RuntimeError):
    """Raised when the demo control plane cannot be trusted."""


@dataclass(frozen=True)
class DemoControlState:
    enabled: bool
    mode: str
    updated_at: str | None
    updated_by: str | None
    runtime_heartbeat_at: str | None
    runtime_id: str | None

    @property
    def runtime_online(self) -> bool:
        if not self.runtime_heartbeat_at:
            return False
        try:
            heartbeat = datetime.fromisoformat(self.runtime_heartbeat_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        if heartbeat.tzinfo is None:
            return False
        # A heartbeat older than 15 seconds is not safe to advertise as live.
        from datetime import timezone
        age = datetime.now(timezone.utc) - heartbeat.astimezone(timezone.utc)
        return age.total_seconds() <= 15.0


class DemoControlClient:
    """Read/update the shared demo auto-trading control state over HTTPS."""

    def __init__(self, base_url: str, token: str, *, timeout: float = 3.0, opener=None) -> None:
        if not base_url or not base_url.startswith(("https://", "http://")):
            raise ValueError("base_url must be an absolute HTTP(S) URL")
        if not token:
            raise ValueError("control token must not be empty")
        if timeout <= 0:
            raise ValueError("timeout must be > 0")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = float(timeout)
        self._opener = opener or urllib.request.urlopen
        self.runtime_id = f"runtime-{secrets.token_hex(8)}"

    def get_state(self) -> DemoControlState:
        payload = self._request("GET", "/api/auto-trading")
        state = self._parse_state(payload)
        if state.mode != "DEMO_ONLY":
            raise DemoControlError("control plane mode is not DEMO_ONLY")
        return state

    def set_enabled(self, enabled: bool, *, source: str = "webaria") -> DemoControlState:
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be bool")
        payload = self._request(
            "POST",
            "/api/auto-trading",
            json_body={"enabled": enabled, "source": source},
        )
        state = self._parse_state(payload)
        if state.mode != "DEMO_ONLY":
            raise DemoControlError("control plane mode is not DEMO_ONLY")
        return state

    def heartbeat(self) -> DemoControlState:
        payload = self._request(
            "POST",
            "/api/auto-trading/heartbeat",
            headers={"x-aria-runtime-id": self.runtime_id},
        )
        state = self._parse_state(payload)
        if state.mode != "DEMO_ONLY":
            raise DemoControlError("control plane mode is not DEMO_ONLY")
        return state

    def is_enabled(self) -> bool:
        """Return False for every control-plane failure (fail closed)."""
        try:
            return self.get_state().enabled
        except (DemoControlError, OSError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
            return False

    def _request(self, method: str, path: str, *, json_body: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
        body = None if json_body is None else json.dumps(json_body).encode("utf-8")
        request_headers = {
            "accept": "application/json",
            "authorization": f"Bearer {self.token}",
        }
        if body is not None:
            request_headers["content-type"] = "application/json"
        if headers:
            request_headers.update(headers)
        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            headers=request_headers,
            method=method,
        )
        try:
            with self._opener(request, timeout=self.timeout) as response:
                raw = response.read()
                payload = json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise DemoControlError(f"control request returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise DemoControlError(f"control request failed: {exc}") from exc
        if not isinstance(payload, dict):
            raise DemoControlError("control response must be a JSON object")
        if "error" in payload:
            raise DemoControlError(str(payload["error"]))
        return payload

    @staticmethod
    def _parse_state(payload: dict[str, Any]) -> DemoControlState:
        if not isinstance(payload.get("enabled"), bool):
            raise DemoControlError("control response has invalid enabled field")
        if not isinstance(payload.get("mode"), str):
            raise DemoControlError("control response has invalid mode field")
        for key in ("updatedAt", "updatedBy", "runtimeHeartbeatAt", "runtimeId"):
            value = payload.get(key)
            if value is not None and not isinstance(value, str):
                raise DemoControlError(f"control response has invalid {key} field")
        return DemoControlState(
            enabled=payload["enabled"],
            mode=payload["mode"],
            updated_at=payload.get("updatedAt"),
            updated_by=payload.get("updatedBy"),
            runtime_heartbeat_at=payload.get("runtimeHeartbeatAt"),
            runtime_id=payload.get("runtimeId"),
        )


__all__ = ["DemoControlClient", "DemoControlError", "DemoControlState"]
