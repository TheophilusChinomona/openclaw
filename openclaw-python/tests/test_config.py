"""Tests for config schema loading and validation."""

import textwrap
from pathlib import Path

import pytest
import yaml

from openclaw.config.schema import (
    AgentConfig,
    BindingConfig,
    BindingMatch,
    ChannelConfig,
    GatewayConfig,
    ModelProviderConfig,
    SecurityConfig,
    ServerConfig,
    SessionConfig,
)


def test_default_gateway_config():
    cfg = GatewayConfig()
    assert cfg.channels == []
    assert cfg.agents == []
    assert cfg.bindings == []
    assert cfg.server.port == 18789
    assert cfg.server.bind == "loopback"
    assert cfg.session.max_context_tokens == 8192
    assert cfg.security.auth_mode == "token"


def test_model_provider_defaults():
    mp = ModelProviderConfig()
    assert mp.type == "openai"
    assert mp.model == "gpt-4o"
    assert mp.api_key is None
    assert mp.base_url is None


def test_channel_config():
    ch = ChannelConfig(id="tg", type="telegram", token="abc123")
    assert ch.id == "tg"
    assert ch.dm_scope == "main"


def test_agent_config_default():
    agent = AgentConfig(id="main")
    assert agent.default is False
    assert agent.skills == []


def test_binding_config():
    b = BindingConfig(agent_id="main", match=BindingMatch(channel="telegram-main"))
    assert b.agent_id == "main"
    assert b.match.channel == "telegram-main"
    assert b.match.guild_id is None


def test_load_from_yaml(tmp_path: Path):
    config_yaml = textwrap.dedent("""\
        model_provider:
          type: openai
          model: gpt-4o-mini
          api_key: sk-test

        channels:
          - id: telegram-main
            type: telegram
            token: "123:abc"
            dm_scope: per-peer

        agents:
          - id: main
            default: true
            system_prompt: "You are helpful."

        bindings:
          - agent_id: main
            match:
              channel: telegram-main

        session:
          max_context_tokens: 4096

        server:
          port: 18790
          bind: lan
    """)
    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_yaml)

    from openclaw.config.loader import load_config

    cfg = load_config(str(config_file))
    assert cfg.model_provider.type == "openai"
    assert cfg.model_provider.model == "gpt-4o-mini"
    assert cfg.model_provider.api_key == "sk-test"
    assert len(cfg.channels) == 1
    assert cfg.channels[0].id == "telegram-main"
    assert cfg.channels[0].dm_scope == "per-peer"
    assert len(cfg.agents) == 1
    assert cfg.agents[0].default is True
    assert len(cfg.bindings) == 1
    assert cfg.bindings[0].agent_id == "main"
    assert cfg.session.max_context_tokens == 4096
    assert cfg.server.port == 18790
    assert cfg.server.bind == "lan"


def test_pydantic_rejects_invalid_port():
    with pytest.raises(Exception):
        ServerConfig(port=-1, bind="loopback")


def test_security_config():
    s = SecurityConfig(auth_mode="none")
    assert s.auth_mode == "none"
    assert s.token is None
