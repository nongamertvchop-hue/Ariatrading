from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from .alerts import TelegramNotifier
from .config import BotConfig
from .rate_limit import TokenBucket
from .storage import SQLiteStore


class BotService:
    """Operational facade around the existing strategy/paper runtime."""

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.store = SQLiteStore(config.sqlite_path)
        self.provider_limit = TokenBucket(config.max_request_rate, config.max_burst)
        self.telegram = TelegramNotifier(config.telegram_token, config.telegram_chat_id, config.notifier_enabled)
        self.started_at = time.time()
        self.last_heartbeat = self.started_at
        self.state = "STARTING"

    def heartbeat(self, **extra: Any) -> dict[str, Any]:
        self.last_heartbeat = time.time()
        payload = {"status": self.state, "mode": self.config.mode, "uptime_s": round(time.time() - self.started_at, 3), "heartbeat_at": datetime.now(timezone.utc).isoformat()}
        payload.update(extra)
        self.store.set_state("heartbeat", payload)
        return payload

    def emit(self, event_type: str, payload: dict[str, Any], *, alert: bool = False) -> int:
        event_id = self.store.append_event(event_type, payload)
        if alert:
            message = f"Ariatrading [{self.config.mode}] {event_type}\n{payload}"
            self.telegram.send(message)
        return event_id

    def authorize_provider_call(self) -> None:
        if not self.provider_limit.allow():
            raise RuntimeError("external provider rate limit reached")

    def set_state(self, state: str, reason: str = "") -> None:
        self.state = str(state)
        self.store.set_state("runtime_state", {"state": self.state, "reason": reason, "at": datetime.now(timezone.utc).isoformat()})

    def close(self) -> None:
        self.store.close()
