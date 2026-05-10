"""GatewayServer — aiohttp app wiring channels, agents, and the event loop."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import web

from openclaw.config.schema import GatewayConfig

logger = logging.getLogger(__name__)


def _make_auth_middleware(cfg: GatewayConfig) -> web.middleware:
    @web.middleware
    async def auth_middleware(request: web.Request, handler: Any) -> web.Response:
        # /healthz is always public
        if request.path == "/healthz":
            return await handler(request)

        if cfg.security.auth_mode == "token" and cfg.security.token:
            auth_header = request.headers.get("Authorization", "")
            expected = f"Bearer {cfg.security.token}"
            if auth_header != expected:
                raise web.HTTPUnauthorized(text="Invalid or missing token")

        return await handler(request)

    return auth_middleware


class GatewayServer:
    def __init__(self, cfg: GatewayConfig) -> None:
        self._cfg = cfg

    def build_app(self) -> web.Application:
        app = web.Application(middlewares=[_make_auth_middleware(self._cfg)])
        app.router.add_get("/healthz", self._healthz)
        app.router.add_get("/api/status", self._api_status)
        return app

    async def _healthz(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def _api_status(self, request: web.Request) -> web.Response:
        return web.json_response({
            "channels": [c.id for c in self._cfg.channels],
            "agents": [a.id for a in self._cfg.agents],
            "server": {
                "port": self._cfg.server.port,
                "bind": self._cfg.server.bind,
            },
        })

    def run(self) -> None:
        from openclaw.tools.builtin import register_all_builtin_tools
        register_all_builtin_tools()

        app = self.build_app()
        host = self._resolve_host()
        port = self._cfg.server.port
        logger.info("Starting OpenClaw gateway on %s:%d", host, port)
        web.run_app(app, host=host, port=port)

    def _resolve_host(self) -> str:
        bind = self._cfg.server.bind
        if bind == "loopback":
            return "127.0.0.1"
        if bind == "lan":
            return "0.0.0.0"
        return self._cfg.server.custom_bind_host or "127.0.0.1"
