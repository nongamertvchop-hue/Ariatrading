"""Deterministic identity for a realtime signal event.

The canonical representation intentionally mirrors worker/signal_event.js.
It is a deduplication identity, not an authorization or security token.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


def canonical_signal_event(payload: Mapping[str, Any]) -> str:
    """Return the stable JSON representation used for event identity."""
    zone = payload.get("zone")
    zone_value = None
    if zone is not None:
        zone_value = [
            zone.get("kind"),
            zone.get("low"),
            zone.get("high"),
            zone.get("touches"),
        ]

    candles = payload.get("candles") or []
    last_candle = candles[-1] if candles else None
    bar_time = payload.get("bar_time")
    if bar_time is None and last_candle is not None:
        bar_time = last_candle.get("datetime")
        if bar_time is None:
            bar_time = last_candle.get("time")

    values = [
        payload.get("symbol"),
        payload.get("timeframe"),
        bar_time,
        payload.get("signal"),
        payload.get("state"),
        payload.get("breakout_state"),
        payload.get("price"),
        payload.get("entry_reference"),
        payload.get("stop_reference"),
        payload.get("structure_bias"),
        (payload.get("score") or {}).get("total") if payload.get("score") else None,
        zone_value,
    ]
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"))


def build_signal_event_id(payload: Mapping[str, Any]) -> str:
    """Build the deterministic event ID shared with the Worker implementation."""
    canonical = canonical_signal_event(payload)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sig_{digest[:32]}"
