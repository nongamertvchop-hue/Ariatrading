from __future__ import annotations

import asyncio
import ipaddress
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse


def create_app(
    *,
    health_provider: Callable[[], dict[str, Any]],
    event_provider: Callable[[], list[dict[str, Any]]],
    market_provider: Callable[[str, str, int], dict[str, Any]] | None = None,
    allowed_ips: tuple[str, ...] = (),
    api_token: str = "",
) -> FastAPI:
    """Build the runtime API with fail-closed optional market/auth boundaries."""
    app = FastAPI(title="Ariatrading Runtime API", docs_url=None, redoc_url=None)
    networks = tuple(ipaddress.ip_network(x, strict=False) for x in allowed_ips)

    def allowed(host: str) -> bool:
        if not networks:
            return True
        try:
            addr = ipaddress.ip_address(host)
        except ValueError:
            return False
        return any(addr in network for network in networks)

    def authorized(request: Request) -> bool:
        if not api_token:
            return True
        return request.headers.get("authorization", "") == f"Bearer {api_token}"

    @app.middleware("http")
    async def request_guard(request: Request, call_next):
        host = request.client.host if request.client else ""
        if not allowed(host):
            return JSONResponse({"detail": "forbidden"}, status_code=403)
        if not authorized(request):
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
        return await call_next(request)

    @app.get("/health")
    async def health():
        return health_provider()

    @app.get("/events")
    async def events(limit: int = 100):
        return {"events": event_provider()[: max(1, min(limit, 1000))]}

    @app.get("/market")
    async def market(symbol: str = "EURUSD", timeframe: str = "15m", count: int = 100):
        if market_provider is None:
            return JSONResponse({"error": "market_unavailable", "message": "MT5 market provider is not configured"}, status_code=503)
        try:
            return market_provider(symbol, timeframe, max(21, min(count, 500)))
        except (ValueError, RuntimeError) as exc:
            return JSONResponse({"error": "market_unavailable", "message": str(exc)}, status_code=503)

    @app.websocket("/ws/events")
    async def event_stream(websocket: WebSocket):
        host = websocket.client.host if websocket.client else ""
        if not allowed(host):
            await websocket.close(code=1008)
            return
        if api_token and websocket.headers.get("authorization", "") != f"Bearer {api_token}":
            await websocket.close(code=1008)
            return
        await websocket.accept()
        try:
            while True:
                await websocket.send_json({"events": event_provider()[:100]})
                await asyncio.sleep(1)
        except Exception:
            try:
                await websocket.close()
            except Exception:
                pass

    return app
