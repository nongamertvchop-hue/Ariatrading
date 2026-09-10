"""HTTP adapter for the realtime closed-candle paper runtime.

The adapter consumes the repository's existing `/api/signal` JSON contract and
exposes only completed OHLC candles to RealtimeMonitor. It has no broker role.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from strategy.realtime import LiveBar


class HttpClosedCandleFeed:
    def __init__(self, base_url: str, *, timeout_seconds: float = 5.0) -> None:
        if not base_url:
            raise ValueError("base_url must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def closed_bars(self, symbol: str, timeframe: str, count: int):
        query = urlencode({"symbol": symbol, "timeframe": timeframe, "count": count})
        request = Request(
            f"{self.base_url}?{query}",
            headers={"accept": "application/json", "cache-control": "no-cache"},
            method="GET",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            if response.status != 200:
                raise RuntimeError(f"closed-candle feed HTTP {response.status}")
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("error"):
            raise RuntimeError(str(payload.get("message") or "closed-candle feed returned an error"))

        raw_candles = payload.get("candles")
        if not isinstance(raw_candles, list):
            raise RuntimeError("closed-candle feed returned no candles")
        bars = []
        for raw in raw_candles:
            timestamp = _parse_timestamp(raw.get("datetime") or raw.get("time"))
            bars.append(
                LiveBar(
                    time=timestamp,
                    open=float(raw["open"]),
                    high=float(raw["high"]),
                    low=float(raw["low"]),
                    close=float(raw["close"]),
                )
            )
        return bars


def _parse_timestamp(value: str | int | float) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("feed timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


__all__ = ["HttpClosedCandleFeed"]
