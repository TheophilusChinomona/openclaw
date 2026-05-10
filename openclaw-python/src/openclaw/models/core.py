"""Core data models shared across the gateway."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal


class ChatType(StrEnum):
    DIRECT = "direct"
    GROUP = "group"
    CHANNEL = "channel"
    THREAD = "thread"


@dataclass
class RoutePeer:
    kind: ChatType
    id: str


@dataclass
class PlatformMessage:
    """Normalized inbound message from any channel adapter."""

    channel: str
    account_id: str
    peer: RoutePeer
    text: str
    message_id: str
    thread_id: str | None = None
    guild_id: str | None = None
    team_id: str | None = None
    member_role_ids: list[str] = field(default_factory=list)
    attachments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentMessage:
    """A single turn in an agent session (user, assistant, or tool)."""

    session_key: str
    agent_id: str
    role: Literal["user", "assistant", "tool"]
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentResponse:
    """Final response from the agent loop."""

    text: str
    session_key: str
    agent_id: str
    tool_calls_made: int = 0
