from __future__ import annotations

from typing import Any


class CCXTGateway:
    """Optional exchange gateway kept separate from the MT5 Forex path."""

    def __init__(self, exchange_id: str, api_key: str = "", api_secret: str = "", *, sandbox: bool = True) -> None:
        try:
            import ccxt  # type: ignore
        except ImportError as exc:
            raise RuntimeError("ccxt is not installed; install requirements-bot.txt") from exc
        exchange_cls = getattr(ccxt, exchange_id, None)
        if exchange_cls is None:
            raise ValueError(f"unsupported ccxt exchange: {exchange_id}")
        self.exchange = exchange_cls({"apiKey": api_key, "secret": api_secret, "enableRateLimit": True})
        if sandbox and hasattr(self.exchange, "set_sandbox_mode"):
            self.exchange.set_sandbox_mode(True)

    def markets(self) -> dict[str, Any]:
        return self.exchange.load_markets()

    def ticker(self, symbol: str) -> dict[str, Any]:
        return self.exchange.fetch_ticker(symbol)

    def ohlcv(self, symbol: str, timeframe: str = "1m", limit: int = 200) -> list[list[Any]]:
        return self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

    def close(self) -> None:
        close = getattr(self.exchange, "close", None)
        if close is not None:
            close()
