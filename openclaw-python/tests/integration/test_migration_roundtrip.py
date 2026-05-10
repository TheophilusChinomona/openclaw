"""Integration: Hermes config → migrate → written YAML → load_config → server up.

The entire migration → load → run path must work end-to-end without errors.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from openclaw.config.loader import load_config
from openclaw.config.schema import BindingConfig, BindingMatch, ChannelConfig, ServerConfig
from openclaw.migration.hermes import migrate_hermes_config
from openclaw.server.gateway import GatewayServer


HERMES_CONFIG = textwrap.dedent("""\
    model_provider:
      type: openai
      api_key: sk-hermes-key
      model: gpt-4o-mini

    agents:
      - id: main
        default: true
        system_prompt: "You are Hermes."
        skills:
          - researcher
        workspace: ~/.hermes/workspaces/main

    session:
      max_context_tokens: 4096
      prune_after: 14d

    security:
      auth_mode: token
      token: hermes-secret
""")


@pytest.fixture
def hermes_config_file(tmp_path: Path) -> Path:
    p = tmp_path / "hermes.yaml"
    p.write_text(HERMES_CONFIG)
    return p


@pytest.fixture
def migrated_config_path(tmp_path: Path, hermes_config_file: Path) -> Path:
    out = tmp_path / "openclaw.yaml"
    result = migrate_hermes_config(
        source_path=str(hermes_config_file),
        channels=[
            ChannelConfig(id="discord-main", type="discord", token="${DISCORD_TOKEN}", dm_scope="per-peer")
        ],
        bindings=[
            BindingConfig(agent_id="main", match=BindingMatch(channel="discord-main", account_id="*"))
        ],
        server=ServerConfig(port=18799, bind="loopback"),
    )
    result.write(str(out))
    return out


def test_migrated_yaml_loads_without_error(migrated_config_path: Path) -> None:
    cfg = load_config(str(migrated_config_path))
    assert cfg.model_provider.model == "gpt-4o-mini"
    assert cfg.model_provider.api_key == "sk-hermes-key"


def test_migrated_config_preserves_agents(migrated_config_path: Path) -> None:
    cfg = load_config(str(migrated_config_path))
    assert len(cfg.agents) == 1
    agent = cfg.agents[0]
    assert agent.id == "main"
    assert agent.default is True
    assert agent.system_prompt == "You are Hermes."
    assert "researcher" in agent.skills


def test_migrated_config_preserves_session_and_security(migrated_config_path: Path) -> None:
    cfg = load_config(str(migrated_config_path))
    assert cfg.session.max_context_tokens == 4096
    assert cfg.session.prune_after == "14d"
    assert cfg.security.auth_mode == "token"
    assert cfg.security.token == "hermes-secret"


def test_migrated_config_has_injected_channel(migrated_config_path: Path) -> None:
    cfg = load_config(str(migrated_config_path))
    assert len(cfg.channels) == 1
    ch = cfg.channels[0]
    assert ch.id == "discord-main"
    assert ch.type == "discord"
    assert ch.dm_scope == "per-peer"


def test_migrated_config_has_binding(migrated_config_path: Path) -> None:
    cfg = load_config(str(migrated_config_path))
    assert len(cfg.bindings) == 1
    assert cfg.bindings[0].agent_id == "main"
    assert cfg.bindings[0].match.channel == "discord-main"


@pytest.mark.asyncio
async def test_migrated_config_server_starts(migrated_config_path: Path) -> None:
    """The migrated config must produce a working GatewayServer."""
    cfg = load_config(str(migrated_config_path))
    app = GatewayServer(cfg).build_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/healthz")
        assert resp.status == 200

        resp2 = await client.get(
            "/api/status", headers={"Authorization": "Bearer hermes-secret"}
        )
        assert resp2.status == 200
        data = await resp2.json()
        assert "discord-main" in data["channels"]
        assert "main" in data["agents"]
