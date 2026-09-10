from __future__ import annotations

import asyncio
import ipaddress
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse


def create_app(*, health_provider: Callable[[], dict[str, Any]], event_provider: Callable[[], list[dict[str, Any]]], allowed_ips: tuple[str, ...] = ()) -> FastAPI:
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

    @app.middleware("http")
    async def ip_guard(request: Request, call_next):
        host = request.client.host if request.client else ""
        if not allowed(host):
            return JSONResponse({"detail": "forbidden"}, status_code=403)
        return await call_next(request)

    @app.get("/health")
    async def health():
        return health_provider()

    @app.get("/events")
    async def events(limit: int = 100):
        return {"events": event_provider()[: max(1, min(limit, 1000))]}

    @app.websocket("/ws/events")
    async def event_stream(websocket: WebSocket):
        host = websocket.client.host if websocket.client else ""
        if not allowed(host):
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
