"""Tests for the Hermes → OpenClaw migration wizard."""

import textwrap
from pathlib import Path

import pytest
import yaml

from openclaw.migration.hermes import migrate_hermes_config, MigrationResult


HERMES_CONFIG = textwrap.dedent("""\
    model_provider:
      type: openai
      api_key: sk-test-key
      model: gpt-4o-mini

    agents:
      - id: main
        default: true
        system_prompt: "You are a helpful assistant."
        skills:
          - researcher
        workspace: ~/.hermes/workspaces/main
      - id: coder
        system_prompt: "You write clean code."

    session:
      max_context_tokens: 4096
      prune_after: 7d

    security:
      auth_mode: token
      token: secret-gateway-token
""")


def write_hermes_config(tmp_path: Path, content: str = HERMES_CONFIG) -> Path:
    p = tmp_path / "hermes_config.yaml"
    p.write_text(content)
    return p


def test_migrate_preserves_model_provider(tmp_path: Path):
    src = write_hermes_config(tmp_path)
    result = migrate_hermes_config(
        source_path=str(src),
        channels=[],
        bindings=[],
    )
    assert result.config.model_provider.type == "openai"
    assert result.config.model_provider.model == "gpt-4o-mini"
    assert result.config.model_provider.api_key == "sk-test-key"


def test_migrate_preserves_agents(tmp_path: Path):
    src = write_hermes_config(tmp_path)
    result = migrate_hermes_config(source_path=str(src), channels=[], bindings=[])
    assert len(result.config.agents) == 2
    assert result.config.agents[0].id == "main"
    assert result.config.agents[0].default is True
    assert "researcher" in result.config.agents[0].skills
    assert result.config.agents[1].id == "coder"


def test_migrate_preserves_session(tmp_path: Path):
    src = write_hermes_config(tmp_path)
    result = migrate_hermes_config(source_path=str(src), channels=[], bindings=[])
    assert result.config.session.max_context_tokens == 4096
    assert result.config.session.prune_after == "7d"


def test_migrate_preserves_security(tmp_path: Path):
    src = write_hermes_config(tmp_path)
    result = migrate_hermes_config(source_path=str(src), channels=[], bindings=[])
    assert result.config.security.auth_mode == "token"
    assert result.config.security.token == "secret-gateway-token"


def test_migrate_injects_discord_channel(tmp_path: Path):
    src = write_hermes_config(tmp_path)
    from openclaw.config.schema import ChannelConfig
    result = migrate_hermes_config(
        source_path=str(src),
        channels=[ChannelConfig(id="discord-main", type="discord", token="${DISCORD_TOKEN}", dm_scope="per-peer")],
        bindings=[],
    )
    assert len(result.config.channels) == 1
    assert result.config.channels[0].id == "discord-main"
    assert result.config.channels[0].dm_scope == "per-peer"


def test_migrate_injects_bindings(tmp_path: Path):
    src = write_hermes_config(tmp_path)
    from openclaw.config.schema import BindingConfig, BindingMatch, ChannelConfig
    result = migrate_hermes_config(
        source_path=str(src),
        channels=[ChannelConfig(id="discord-main", type="discord", token="tok", dm_scope="per-peer")],
        bindings=[BindingConfig(agent_id="main", match=BindingMatch(channel="discord-main", account_id="*"))],
    )
    assert len(result.config.bindings) == 1
    assert result.config.bindings[0].agent_id == "main"


def test_migrate_writes_valid_yaml(tmp_path: Path):
    src = write_hermes_config(tmp_path)
    out = tmp_path / "openclaw_config.yaml"
    result = migrate_hermes_config(source_path=str(src), channels=[], bindings=[])
    result.write(str(out))
    written = yaml.safe_load(out.read_text())
    assert written["model_provider"]["model"] == "gpt-4o-mini"
    assert len(written["agents"]) == 2


def test_migrate_reports_skill_dirs(tmp_path: Path):
    src = write_hermes_config(tmp_path)
    result = migrate_hermes_config(source_path=str(src), channels=[], bindings=[])
    # Should surface the workspace path from the original config
    assert any("main" in w for w in result.skill_workspace_hints)


def test_migrate_missing_source_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        migrate_hermes_config(source_path=str(tmp_path / "nonexistent.yaml"), channels=[], bindings=[])


def test_migrate_minimal_hermes_config(tmp_path: Path):
    """A Hermes config with only model_provider should migrate without errors."""
    minimal = textwrap.dedent("""\
        model_provider:
          type: openai
          model: gpt-4o
    """)
    src = write_hermes_config(tmp_path, content=minimal)
    result = migrate_hermes_config(source_path=str(src), channels=[], bindings=[])
    assert result.config.model_provider.model == "gpt-4o"
    assert len(result.config.agents) == 0
