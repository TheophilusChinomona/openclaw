"""Tests for GatewayServer — healthz endpoint and auth gate."""

import pytest
from aiohttp.test_utils import TestClient, TestServer

from openclaw.config.schema import GatewayConfig, SecurityConfig
from openclaw.server.gateway import GatewayServer


def make_server(auth_mode: str = "none", token: str | None = None) -> GatewayServer:
    cfg = GatewayConfig(security=SecurityConfig(auth_mode=auth_mode, token=token))
    return GatewayServer(cfg)


@pytest.mark.asyncio
async def test_healthz_returns_200():
    server = make_server(auth_mode="none")
    app = server.build_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/healthz")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_healthz_works_without_token_when_auth_none():
    server = make_server(auth_mode="none")
    app = server.build_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/healthz")
        assert resp.status == 200


@pytest.mark.asyncio
async def test_protected_endpoint_rejects_without_token():
    server = make_server(auth_mode="token", token="secret123")
    app = server.build_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/api/status")
        assert resp.status == 401


@pytest.mark.asyncio
async def test_protected_endpoint_accepts_valid_token():
    server = make_server(auth_mode="token", token="secret123")
    app = server.build_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.get(
            "/api/status",
            headers={"Authorization": "Bearer secret123"},
        )
        assert resp.status == 200
