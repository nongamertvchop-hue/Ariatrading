from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from dotenv import load_dotenv
import uvicorn

from adapters.mt5_feed import MT5BarFeed
from bot.config import BotConfig
from bot.health_api import create_app
from bot.service import BotService


load_dotenv()
config = BotConfig.from_env()
service = BotService(config)
service.set_state("RUNNING")

_feed: MT5BarFeed | None = None
_feed_lock = Lock()


def _finite_positive(value: Any, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise RuntimeError(f"MT5 returned invalid {name}")
    return number


def market_provider(symbol: str, timeframe: str, count: int) -> dict[str, Any]:
    """Read broker candles without exposing any execution capability."""
    global _feed
    broker_symbol = symbol.replace("/", "").upper()
    with _feed_lock:
        if _feed is None:
            _feed = MT5BarFeed(terminal_path=config.mt5_terminal_path or None)
        bars = _feed.closed_bars(broker_symbol, timeframe, count)
        forming = _feed.current_bar(broker_symbol, timeframe)
        tick = _feed.last_tick(broker_symbol)

    if not bars:
        raise RuntimeError(f"MT5 returned no completed candles for {broker_symbol}")

    def candle(bar: Any) -> dict[str, Any]:
        return {
            "datetime": bar.time.astimezone(timezone.utc).isoformat(),
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
        }

    price_candidates = (tick.get("last"), tick.get("bid"), tick.get("ask"))
    price = next((float(value) for value in price_candidates if value is not None and math.isfinite(float(value)) and float(value) > 0), None)
    if price is None:
        bid = float(tick.get("bid", 0))
        ask = float(tick.get("ask", 0))
        if math.isfinite(bid) and math.isfinite(ask) and bid > 0 and ask > 0:
            price = (bid + ask) / 2.0
    if price is None or not math.isfinite(price) or price <= 0:
        raise RuntimeError(f"MT5 returned invalid price for {broker_symbol}")

    # `candles` contains completed bars only. `live_candle` comes from MT5's
    # actual forming bar, then incorporates the newest tick for prompt display.
    live_open = float(forming.open)
    live_high = max(float(forming.high), price)
    live_low = min(float(forming.low), price)
    live = {
        "datetime": forming.time.astimezone(timezone.utc).isoformat(),
        "open": live_open,
        "high": live_high,
        "low": live_low,
        "close": price,
    }
    for name, value in (("live open", live_open), ("live high", live_high), ("live low", live_low), ("live close", price)):
        _finite_positive(value, name)

    return {
        "symbol": symbol,
        "broker_symbol": broker_symbol,
        "timeframe": timeframe,
        "candles": [candle(bar) for bar in bars],
        "live_candle": live,
        "price": price,
        "tick": {
            "time": tick["time"].astimezone(timezone.utc).isoformat(),
            "bid": float(tick["bid"]),
            "ask": float(tick["ask"]),
            "spread": float(tick["ask"]) - float(tick["bid"]),
        },
        "source": "mt5",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "execution": "NONE",
    }


app = create_app(
    health_provider=lambda: service.heartbeat(),
    event_provider=lambda: service.store.recent_events(100),
    market_provider=market_provider,
    allowed_ips=config.allowed_ips,
    api_token=os.getenv("RUNTIME_API_TOKEN", "").strip(),
)


if __name__ == "__main__":
    uvicorn.run(app, host=config.health_host, port=config.health_port, log_level="info")
