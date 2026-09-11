"""Read-only HTTP bridge from a local MetaTrader 5 terminal to Webaria.

This process reads market data from a local MetaTrader 5 terminal. It can serve
that data locally and, when `MT5_INGEST_URL` is configured, continuously push the
same payload to the Webaria `/api/mt5/ingest` endpoint. It never calls
order_check/order_send and never changes trading state.

Run this on the same Windows host as the MT5 terminal. Keep the bridge token out
of Git. The hosted Webaria path should receive data through the authenticated
HTTPS ingest endpoint instead of exposing the MT5 machine directly.
"""

from __future__ import annotations

import json
import math
import os
import secrets
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

try:
    import MetaTrader5 as mt5  # type: ignore
except ImportError:  # pragma: no cover - deployment host dependency
    mt5 = None

TIMEFRAME_MAP = {
    "1m": "TIMEFRAME_M1",
    "5m": "TIMEFRAME_M5",
    "15m": "TIMEFRAME_M15",
    "30m": "TIMEFRAME_M30",
    "1h": "TIMEFRAME_H1",
    "4h": "TIMEFRAME_H4",
    "1D": "TIMEFRAME_D1",
}
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787
DEFAULT_COUNT = 100
MAX_COUNT = 500
DEFAULT_PUSH_INTERVAL_SECONDS = 3.0


def _env_token() -> str:
    token = os.getenv("MT5_MARKET_BRIDGE_TOKEN", "").strip()
    if len(token) < 24:
        raise RuntimeError("MT5_MARKET_BRIDGE_TOKEN must be configured with at least 24 characters")
    return token


def _require_mt5() -> Any:
    if mt5 is None:
        raise RuntimeError("MetaTrader5 package is required; install requirements-realtime.txt")
    return mt5


def _timeframe_value(value: str) -> Any:
    raw = TIMEFRAME_MAP[value]
    if isinstance(raw, str):
        return getattr(_require_mt5(), raw)
    return raw


def _initialize() -> None:
    terminal = _require_mt5()
    terminal_path = os.getenv("MT5_TERMINAL_PATH", "").strip()
    ok = terminal.initialize(path=terminal_path) if terminal_path else terminal.initialize()
    if not ok:
        raise RuntimeError(f"MT5 initialize failed: {terminal.last_error()}")


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
    if not all(math.isfinite(value) for value in values.values()):
        raise ValueError("MT5 returned non-finite OHLC")
    high = values["high"]
    low = values["low"]
    if high < max(values["open"], values["close"]) or low > min(values["open"], values["close"]) or high < low:
        raise ValueError("MT5 returned inconsistent OHLC")
    timestamp = int(getattr(row, "time"))
    if timestamp <= 0:
        raise ValueError("MT5 returned invalid candle timestamp")
    return {"time": timestamp, **values}


def market_payload(symbol: str, timeframe: str, count: int) -> dict[str, Any]:
    terminal = _require_mt5()
    if not terminal.symbol_select(symbol, True):
        raise RuntimeError(f"MT5 symbol_select failed for {symbol}: {terminal.last_error()}")

    rates = terminal.copy_rates_from_pos(symbol, _timeframe_value(timeframe), 1, count)
    live_rates = terminal.copy_rates_from_pos(symbol, _timeframe_value(timeframe), 0, 1)
    if rates is None or live_rates is None:
        raise RuntimeError(f"MT5 copy_rates_from_pos failed: {terminal.last_error()}")

    completed = [_candle(row) for row in rates]
    completed.sort(key=lambda row: row["time"])
    live = _candle(live_rates[-1]) if len(live_rates) else None
    tick = terminal.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"MT5 symbol_info_tick failed: {terminal.last_error()}")

    bid = float(tick.bid)
    ask = float(tick.ask)
    if not (math.isfinite(bid) and math.isfinite(ask) and bid > 0 and ask > 0 and ask >= bid):
        raise RuntimeError("MT5 tick is invalid")
    midpoint = (bid + ask) / 2.0

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "candles": completed[-count:],
        "live_candle": live,
        "price": midpoint,
        "tick": {"time": int(tick.time), "bid": bid, "ask": ask},
        "source": "mt5",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "received_at": int(datetime.now(timezone.utc).timestamp()),
        "execution": "NONE",
    }


def push_to_ingest(payload: dict[str, Any]) -> None:
    target = os.getenv("MT5_INGEST_URL", "").strip()
    if not target:
        raise RuntimeError("MT5_INGEST_URL is not configured")
    token = _env_token()
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = Request(
        target,
        data=body,
        method="POST",
        headers={
            "authorization": f"Bearer {token}",
            "content-type": "application/json",
            "content-length": str(len(body)),
        },
    )
    try:
        with urlopen(request, timeout=8) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"MT5 ingest returned HTTP {response.status}")
    except HTTPError as exc:
        raise RuntimeError(f"MT5 ingest HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"MT5 ingest connection failed: {exc.reason}") from exc


def _configured_symbols() -> tuple[str, ...]:
    raw = os.getenv("MT5_MARKET_SYMBOLS", "EURUSD")
    symbols = tuple(_symbol_name(item) for item in raw.split(",") if item.strip())
    if not symbols or len(set(symbols)) != len(symbols):
        raise RuntimeError("MT5_MARKET_SYMBOLS must contain unique MT5 symbols")
    return symbols


def _configured_timeframes() -> tuple[str, ...]:
    raw = os.getenv("MT5_MARKET_TIMEFRAMES", "1m,5m,15m,30m,1h,4h,1D")
    values = tuple(_timeframe(item) for item in raw.split(",") if item.strip())
    if not values or len(set(values)) != len(values):
        raise RuntimeError("MT5_MARKET_TIMEFRAMES must contain unique supported timeframes")
    return values


def publish_loop(stop_event: threading.Event) -> None:
    interval = float(os.getenv("MT5_PUSH_INTERVAL_SECONDS", str(DEFAULT_PUSH_INTERVAL_SECONDS)))
    if not math.isfinite(interval) or interval < 1.0:
        raise RuntimeError("MT5_PUSH_INTERVAL_SECONDS must be finite and >= 1 second")
    symbols = _configured_symbols()
    timeframes = _configured_timeframes()

    while not stop_event.is_set():
        cycle_started = time.monotonic()
        for symbol in symbols:
            for timeframe in timeframes:
                try:
                    payload = market_payload(symbol, timeframe, DEFAULT_COUNT)
                    push_to_ingest(payload)
                except Exception as exc:
                    print(f"MT5 ingest failed for {symbol} {timeframe}: {exc}")
        elapsed = time.monotonic() - cycle_started
        stop_event.wait(max(0.0, interval - elapsed))


class Handler(BaseHTTPRequestHandler):
    server_version = "AriatradingMT5Bridge/1.1"

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
    terminal = _require_mt5()
    _initialize()
    host = os.getenv("MT5_MARKET_BRIDGE_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST
    port = int(os.getenv("MT5_MARKET_BRIDGE_PORT", str(DEFAULT_PORT)))
    server = ThreadingHTTPServer((host, port), Handler)
    stop_event = threading.Event()
    publisher = None
    if os.getenv("MT5_INGEST_URL", "").strip():
        publisher = threading.Thread(target=publish_loop, args=(stop_event,), name="mt5-market-publisher", daemon=True)
        publisher.start()
    print(f"Ariatrading MT5 market bridge listening on http://{host}:{port}/market")
    print("Read-only bridge: order execution is not available from this process.")
    if publisher is not None:
        print("Push mode enabled: MT5 -> Webaria /api/mt5/ingest")
    try:
        server.serve_forever()
    finally:
        stop_event.set()
        if publisher is not None:
            publisher.join(timeout=5)
        server.shutdown()
        terminal.shutdown()


if __name__ == "__main__":
    main()
