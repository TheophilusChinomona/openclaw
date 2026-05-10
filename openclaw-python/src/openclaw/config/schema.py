"""Pydantic config schema for the OpenClaw Python gateway."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ModelProviderConfig(BaseModel):
    type: Literal["openai", "anthropic", "ollama"] = "openai"
    api_key: str | None = None
    model: str = "gpt-4o"
    base_url: str | None = None


class ChannelConfig(BaseModel):
    id: str
    type: Literal["telegram", "discord"]
    token: str
    dm_scope: Literal["main", "per-peer", "per-channel-peer", "per-account-channel-peer"] = "main"


class AgentConfig(BaseModel):
    id: str
    default: bool = False
    system_prompt: str = ""
    workspace: str | None = None
    skills: list[str] = Field(default_factory=list)


class BindingMatch(BaseModel):
    channel: str
    account_id: str | None = None
    peer_kind: str | None = None
    peer_id: str | None = None
    guild_id: str | None = None
    team_id: str | None = None
    roles: list[str] = Field(default_factory=list)


class BindingConfig(BaseModel):
    agent_id: str
    match: BindingMatch


class SessionConfig(BaseModel):
    store: str = "~/.openclaw/sessions"
    max_context_tokens: int = Field(default=8192, ge=256)
    prune_after: str = "30d"


class SecurityConfig(BaseModel):
    auth_mode: Literal["none", "token"] = "token"
    token: str | None = None


class ServerConfig(BaseModel):
    port: int = Field(default=18789, ge=1, le=65535)
    bind: Literal["loopback", "lan", "custom"] = "loopback"
    custom_bind_host: str | None = None


class GatewayConfig(BaseModel):
    model_provider: ModelProviderConfig = Field(default_factory=ModelProviderConfig)
    channels: list[ChannelConfig] = Field(default_factory=list)
    agents: list[AgentConfig] = Field(default_factory=list)
    bindings: list[BindingConfig] = Field(default_factory=list)
    session: SessionConfig = Field(default_factory=SessionConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
