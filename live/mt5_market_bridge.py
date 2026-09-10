"""Read-only HTTP bridge from a local MetaTrader 5 terminal to Webaria.

This process exposes completed MT5 candles and the current bid/ask through a
small authenticated HTTP API. It never calls order_check/order_send and does
not change trading state.

Run this on the same Windows host as the MT5 terminal. Put the endpoint behind
HTTPS/reverse-proxy or a private tunnel before exposing it to Cloudflare.
"""

from __future__ import annotations

import json
import os
import secrets
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

try:
    import MetaTrader5 as mt5  # type: ignore
except ImportError as exc:  # pragma: no cover - exercised on deployment host
    raise RuntimeError("MetaTrader5 package is required; install requirements-realtime.txt") from exc

TIMEFRAME_MAP = {
    "1m": mt5.TIMEFRAME_M1,
    "5m": mt5.TIMEFRAME_M5,
    "15m": mt5.TIMEFRAME_M15,
    "30m": mt5.TIMEFRAME_M30,
    "1h": mt5.TIMEFRAME_H1,
    "4h": mt5.TIMEFRAME_H4,
    "1D": mt5.TIMEFRAME_D1,
}
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787
DEFAULT_COUNT = 100
MAX_COUNT = 500


def _env_token() -> str:
    token = os.getenv("MT5_MARKET_BRIDGE_TOKEN", "").strip()
    if len(token) < 24:
        raise RuntimeError("MT5_MARKET_BRIDGE_TOKEN must be configured with at least 24 characters")
    return token


def _initialize() -> None:
    terminal_path = os.getenv("MT5_TERMINAL_PATH", "").strip()
    ok = mt5.initialize(path=terminal_path) if terminal_path else mt5.initialize()
    if not ok:
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")


def _symbol_name(raw: str) -> str:
    symbol = raw.strip().upper()
    if not symbol.isalnum() or not (6 <= len(symbol) <= 16):
        raise ValueError("symbol must be an MT5 symbol such as EURUSD")
    return symbol


def _timeframe(raw: str) -> str:
    value = raw.strip()
    if value not in TIMEFRAME_MAP:
        raise ValueError(f"unsupported timeframe: {value}")
    return value


def _candle(row: Any) -> dict[str, Any]:
    values = {field: float(getattr(row, field)) for field in ("open", "high", "low", "close")}
    if not all(value == value and abs(value) != float("inf") for value in values.values()):
        raise ValueError("MT5 returned non-finite OHLC")
    high = values["high"]
    low = values["low"]
    if high < max(values["open"], values["close"]) or low > min(values["open"], values["close"]) or high < low:
        raise ValueError("MT5 returned inconsistent OHLC")
    return {"time": int(getattr(row, "time")), **values}


def market_payload(symbol: str, timeframe: str, count: int) -> dict[str, Any]:
    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"MT5 symbol_select failed for {symbol}: {mt5.last_error()}")

    rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME_MAP[timeframe], 1, count)
    if rates is None:
        raise RuntimeError(f"MT5 copy_rates_from_pos failed: {mt5.last_error()}")
    completed = [_candle(row) for row in rates]
    completed.sort(key=lambda row: row["time"])
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"MT5 symbol_info_tick failed: {mt5.last_error()}")

    bid = float(tick.bid)
    ask = float(tick.ask)
    if not (bid > 0 and ask > 0 and ask >= bid):
        raise RuntimeError("MT5 tick is invalid")
    midpoint = (bid + ask) / 2.0
    live = dict(completed[-1]) if completed else None
    if live is not None:
        live["close"] = midpoint
        live["time"] = int(tick.time)
        live["open"] = live["open"]
        live["high"] = max(live["high"], midpoint)
        live["low"] = min(live["low"], midpoint)

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "candles": completed[-count:],
        "live_candle": live,
        "price": midpoint,
        "tick": {
            "time": int(tick.time),
            "bid": bid,
            "ask": ask,
        },
        "source": "mt5",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "received_at": int(datetime.now(timezone.utc).timestamp()),
        "execution": "NONE",
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "AriatradingMT5Bridge/1.0"

    def _json(self, status: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _authorized(self) -> bool:
        presented = self.headers.get("authorization", "")
        expected = _env_token()
        if not presented.lower().startswith("bearer "):
            return False
        return secrets.compare_digest(presented[7:].strip(), expected)

    def do_GET(self) -> None:  # noqa: N802
        try:
            if not self._authorized():
                self._json(401, {"error": "unauthorized"})
                return
            parsed = urlparse(self.path)
            if parsed.path != "/market":
                self._json(404, {"error": "not_found"})
                return
            query = parse_qs(parsed.query)
            symbol = _symbol_name(query.get("symbol", ["EURUSD"])[0])
            timeframe = _timeframe(query.get("timeframe", ["15m"])[0])
            raw_count = int(query.get("count", [str(DEFAULT_COUNT)])[0])
            count = min(max(raw_count, 20), MAX_COUNT)
            self._json(200, market_payload(symbol, timeframe, count))
        except (ValueError, RuntimeError) as exc:
            self._json(503, {"error": "mt5_market_unavailable", "message": str(exc), "source": "mt5", "execution": "NONE"})
        except Exception:
            self._json(500, {"error": "internal_error", "message": "MT5 bridge failed closed", "source": "mt5", "execution": "NONE"})

    def log_message(self, _format: str, *_args: Any) -> None:
        return


def main() -> None:
    _env_token()
    _initialize()
    host = os.getenv("MT5_MARKET_BRIDGE_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST
    port = int(os.getenv("MT5_MARKET_BRIDGE_PORT", str(DEFAULT_PORT)))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Ariatrading MT5 market bridge listening on http://{host}:{port}/market")
    print("Read-only bridge: order execution is not available from this process.")
    try:
        server.serve_forever()
    finally:
        server.shutdown()
        mt5.shutdown()


if __name__ == "__main__":
    main()
