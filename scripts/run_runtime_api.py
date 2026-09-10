from __future__ import annotations

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


def market_provider(symbol: str, timeframe: str, count: int) -> dict[str, Any]:
    """Read broker candles without exposing any execution capability."""
    global _feed
    broker_symbol = symbol.replace("/", "").upper()
    with _feed_lock:
        if _feed is None:
            _feed = MT5BarFeed(terminal_path=config.mt5_terminal_path or None)
        bars = _feed.closed_bars(broker_symbol, timeframe, count)
        tick = _feed.last_tick(broker_symbol)

    if not bars:
        raise RuntimeError(f"MT5 returned no completed candles for {broker_symbol}")

    def candle(bar: Any) -> dict[str, Any]:
        return {
            "datetime": bar.time.astimezone(timezone.utc).isoformat(),
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
        }

    # The forming candle is only a display object. Strategy code must consume
    # `candles`, which contains completed bars exclusively.
    live = {
        "datetime": tick["time"].astimezone(timezone.utc).isoformat(),
        "open": bars[-1].open,
        "high": max(bars[-1].high, tick["last"]),
        "low": min(bars[-1].low, tick["last"]),
        "close": tick["last"],
    }
    return {
        "symbol": symbol,
        "broker_symbol": broker_symbol,
        "timeframe": timeframe,
        "candles": [candle(bar) for bar in bars],
        "live_candle": live,
        "price": tick["last"],
        "tick": {
            "time": tick["time"].astimezone(timezone.utc).isoformat(),
            "bid": tick["bid"],
            "ask": tick["ask"],
            "spread": tick["spread"],
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
