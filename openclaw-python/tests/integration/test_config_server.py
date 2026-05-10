"""Integration: YAML on disk → load_config → GatewayServer → live HTTP endpoints."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from openclaw.config.loader import load_config
from openclaw.server.gateway import GatewayServer


CONFIG_YAML = textwrap.dedent("""\
    model_provider:
      type: openai
      model: gpt-4o
      api_key: sk-fake

    channels:
      - id: discord-main
        type: discord
        token: fake-discord-token
        dm_scope: per-peer

    agents:
      - id: main
        default: true
        system_prompt: "You are helpful."

    bindings:
      - agent_id: main
        match:
          channel: discord-main
          account_id: "*"

    security:
      auth_mode: token
      token: super-secret

    server:
      port: 19999
      bind: loopback
""")


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(CONFIG_YAML)
    return p


@pytest.mark.asyncio
async def test_healthz_from_yaml_config(config_file: Path) -> None:
    cfg = load_config(str(config_file))
    app = GatewayServer(cfg).build_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/healthz")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_status_returns_channels_and_agents(config_file: Path) -> None:
    cfg = load_config(str(config_file))
    app = GatewayServer(cfg).build_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.get(
            "/api/status", headers={"Authorization": "Bearer super-secret"}
        )
        assert resp.status == 200
        data = await resp.json()
        assert "discord-main" in data["channels"]
        assert "main" in data["agents"]
        assert data["server"]["port"] == 19999


@pytest.mark.asyncio
async def test_wrong_token_rejected(config_file: Path) -> None:
    cfg = load_config(str(config_file))
    app = GatewayServer(cfg).build_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.get(
            "/api/status", headers={"Authorization": "Bearer wrong-token"}
        )
        assert resp.status == 401


@pytest.mark.asyncio
async def test_env_var_injection_in_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """${ENV_VAR} placeholders in the YAML are resolved from the environment."""
    monkeypatch.setenv("TEST_API_KEY", "injected-key-xyz")
    cfg_text = textwrap.dedent("""\
        model_provider:
          type: openai
          model: gpt-4o
          api_key: ${TEST_API_KEY}
    """)
    p = tmp_path / "cfg.yaml"
    p.write_text(cfg_text)
    cfg = load_config(str(p))
    assert cfg.model_provider.api_key == "injected-key-xyz"
