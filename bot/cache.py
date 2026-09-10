from __future__ import annotations

import json
from typing import Any


class RedisCache:
    """Optional low-latency cache. Durable trading state must stay in SQLite."""

    def __init__(self, url: str) -> None:
        if not url:
            self.client = None
            return
        try:
            import redis  # type: ignore
        except ImportError as exc:
            raise RuntimeError("redis package is required when REDIS_URL is configured") from exc
        self.client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2, health_check_interval=30)
        self.client.ping()

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def set_json(self, key: str, value: Any, ttl_seconds: int = 60) -> None:
        if self.client is None:
            return
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be >= 1")
        self.client.set(key, json.dumps(value, sort_keys=True, default=str), ex=ttl_seconds)

    def get_json(self, key: str) -> Any | None:
        if self.client is None:
            return None
        raw = self.client.get(key)
        return None if raw is None else json.loads(raw)
