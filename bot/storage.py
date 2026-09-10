from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SQLiteStore:
    """Durable operational store; Redis is never the source of truth."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.execute("""CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL
        )""")
        self._conn.execute("""CREATE TABLE IF NOT EXISTS state(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        self._conn.commit()

    def append_event(self, event_type: str, payload: dict[str, Any]) -> int:
        if not event_type:
            raise ValueError("event_type is required")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            cur = self._conn.execute("INSERT INTO events(ts,event_type,payload) VALUES(?,?,?)", (now, event_type, encoded))
            self._conn.commit()
            return int(cur.lastrowid)

    def set_state(self, key: str, value: Any) -> None:
        if not key:
            raise ValueError("key is required")
        now = datetime.now(timezone.utc).isoformat()
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        with self._lock:
            self._conn.execute(
                "INSERT INTO state(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
                (key, encoded, now),
            )
            self._conn.commit()

    def get_state(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self._conn.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return default if row is None else json.loads(row[0])

    def recent_events(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        with self._lock:
            rows = self._conn.execute("SELECT id,ts,event_type,payload FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{"id": r[0], "ts": r[1], "event_type": r[2], "payload": json.loads(r[3])} for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
