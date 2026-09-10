from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class TokenBucket:
    rate: float = 5.0
    capacity: int = 10

    def __post_init__(self) -> None:
        if self.rate <= 0 or self.capacity < 1:
            raise ValueError("rate and capacity must be positive")
        self.tokens = float(self.capacity)
        self.updated = time.monotonic()
        self._lock = threading.Lock()

    def allow(self, cost: float = 1.0) -> bool:
        if cost <= 0:
            raise ValueError("cost must be > 0")
        now = time.monotonic()
        with self._lock:
            self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
            self.updated = now
            if self.tokens < cost:
                return False
            self.tokens -= cost
            return True

    def wait(self, cost: float = 1.0, timeout: float = 30.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.allow(cost):
                return True
            time.sleep(min(0.1, max(0.01, (cost - self.tokens) / self.rate)))
        return False
