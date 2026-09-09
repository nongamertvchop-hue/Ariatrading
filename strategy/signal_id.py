"""Deterministic Signal Event ID generation and in-memory registry.

Provides stable, reproducible signal identifiers so repeated polling or
replay cannot create duplicate research snapshots. IDs are derived only
from information available at the confirmation bar (no future data).

Educational / research use only.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from .levels_v2 import PriceZone


def _zone_key(zone: PriceZone | None) -> str:
    if zone is None:
        return "none"
    # Stable key from zone identity (kind + rounded bounds + touch count)
    low = f"{zone.low:.5f}"
    high = f"{zone.high:.5f}"
    return f"{zone.kind}:{low}:{high}:{zone.touches}"


def make_signal_id(
    *,
    symbol: str,
    timeframe: str,
    action: str,
    confirmation_index: int | None,
    zone: PriceZone | None = None,
    extra: str = "",
) -> str:
    """Create a deterministic signal event ID.

    The ID is stable across identical inputs and suitable for deduplication.
    Format: sig_<12-char-hex>
    """
    if not symbol:
        raise ValueError("symbol must not be empty")
    if not timeframe:
        raise ValueError("timeframe must not be empty")
    if action not in {"LONG", "SHORT", "WAIT"}:
        raise ValueError("action must be LONG, SHORT, or WAIT")

    conf = "none" if confirmation_index is None else str(confirmation_index)
    payload = f"{symbol}|{timeframe}|{action}|{conf}|{_zone_key(zone)}|{extra}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"sig_{digest}"


@dataclass(frozen=True)
class SignalRecord:
    signal_id: str
    symbol: str
    timeframe: str
    action: str
    first_seen: datetime
    count: int = 1


class SignalRegistry:
    """In-memory registry that tracks seen signal IDs for deduplication."""

    def __init__(self) -> None:
        self._seen: dict[str, SignalRecord] = {}

    def register(
        self,
        signal_id: str,
        *,
        symbol: str,
        timeframe: str,
        action: str,
        now: datetime | None = None,
    ) -> tuple[bool, SignalRecord]:
        """Register a signal ID.

        Returns (is_new, record).
        is_new is True only on the first observation of this ID.
        """
        if now is None:
            now = datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")

        existing = self._seen.get(signal_id)
        if existing is not None:
            updated = SignalRecord(
                signal_id=existing.signal_id,
                symbol=existing.symbol,
                timeframe=existing.timeframe,
                action=existing.action,
                first_seen=existing.first_seen,
                count=existing.count + 1,
            )
            self._seen[signal_id] = updated
            return False, updated

        record = SignalRecord(
            signal_id=signal_id,
            symbol=symbol,
            timeframe=timeframe,
            action=action,
            first_seen=now,
            count=1,
        )
        self._seen[signal_id] = record
        return True, record

    def has(self, signal_id: str) -> bool:
        return signal_id in self._seen

    def get(self, signal_id: str) -> SignalRecord | None:
        return self._seen.get(signal_id)

    def clear(self) -> None:
        self._seen.clear()

    def ids(self) -> Iterable[str]:
        return self._seen.keys()

    def __len__(self) -> int:
        return len(self._seen)
