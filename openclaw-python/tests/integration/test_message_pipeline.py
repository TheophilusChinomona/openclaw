"""Integration: Discord message → router → session → context → agent → response.

Exercises every module boundary in the inbound message path without hitting
a real LLM or real Discord API.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from openclaw.agent.loop import AgentLoop
from openclaw.channels.discord import DiscordChannelAdapter
from openclaw.config.schema import (
    AgentConfig,
    BindingConfig,
    BindingMatch,
    ChannelConfig,
    GatewayConfig,
    SessionConfig,
)
from openclaw.context.engine import ContextEngine
from openclaw.models.core import ChatType
from openclaw.routing.router import GatewayRouter
from openclaw.session.manager import SessionManager


def _make_discord_message(bot_id: int, author_id: int, content: str, is_dm: bool) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    msg.id = 1
    msg.author.id = author_id
    msg.author.bot = False
    if is_dm:
        msg.guild = None
        msg.channel.type.name = "private"
        msg.channel.id = 999
        msg.channel.recipient.id = author_id
    else:
        msg.guild = MagicMock()
        msg.guild.id = 777
        msg.channel.id = 500
        msg.channel.type.name = "text"
    return msg


@pytest.mark.asyncio
async def test_full_dm_pipeline(tmp_path: Path, mock_llm_server: dict[str, Any]) -> None:
    """DM from a Discord user reaches the agent and produces a response."""
    mock_llm_server["responses"].append({
        "choices": [{"message": {"role": "assistant", "content": "Hello from agent!", "tool_calls": None}}]
    })

    # 1. Channel adapter normalises the raw Discord event
    adapter = DiscordChannelAdapter(
        channel_id="discord-main", token="fake", dm_scope="per-peer", bot_id=9999
    )
    raw_msg = _make_discord_message(bot_id=9999, author_id=42, content="hi bot", is_dm=True)
    platform_msg = adapter.normalize_event(raw_msg)
    assert platform_msg is not None

    # 2. Router resolves the session key
    cfg = GatewayConfig(
        channels=[ChannelConfig(id="discord-main", type="discord", token="t", dm_scope="per-peer")],
        agents=[AgentConfig(id="main", default=True)],
        bindings=[BindingConfig(agent_id="main", match=BindingMatch(channel="discord-main", account_id="*"))],
        session=SessionConfig(store=str(tmp_path / "sessions")),
    )
    router = GatewayRouter(cfg)
    route = router.resolve(
        channel=platform_msg.channel,
        peer=platform_msg.peer,
        account_id=platform_msg.account_id,
    )
    assert route.agent_id == "main"
    assert route.session_key.startswith("agent:main:direct:")

    # 3. Agent loop processes the message
    sm = SessionManager(store=str(tmp_path / "sessions"))
    engine = ContextEngine(system_prompt="You are helpful.")
    loop = AgentLoop(
        session_manager=sm,
        context_engine=engine,
        tool_registry={},
        api_base=mock_llm_server["base_url"],
        api_key="sk-test",
        model="gpt-4o",
    )
    response = await loop.run(route.session_key, route.agent_id, platform_msg.text)

    assert response.text == "Hello from agent!"
    assert response.agent_id == "main"
    assert response.tool_calls_made == 0

    # 4. Session was persisted to disk
    msgs = sm.load(route.session_key)
    assert len(msgs) == 2  # user + assistant
    assert msgs[0].role == "user"
    assert msgs[1].role == "assistant"


@pytest.mark.asyncio
async def test_second_turn_includes_history(tmp_path: Path, mock_llm_server: dict[str, Any]) -> None:
    """Second message carries conversation history in the LLM request."""
    mock_llm_server["responses"].extend([
        {"choices": [{"message": {"role": "assistant", "content": "Turn 1.", "tool_calls": None}}]},
        {"choices": [{"message": {"role": "assistant", "content": "Turn 2.", "tool_calls": None}}]},
    ])

    session_key = "agent:main:direct:42"
    sm = SessionManager(store=str(tmp_path / "sessions"))
    engine = ContextEngine(system_prompt="sys")
    loop = AgentLoop(
        session_manager=sm,
        context_engine=engine,
        tool_registry={},
        api_base=mock_llm_server["base_url"],
        api_key="sk-test",
        model="gpt-4o",
    )

    await loop.run(session_key, "main", "first message")
    await loop.run(session_key, "main", "second message")

    # The second LLM request must carry all 3 prior turns (sys + user1 + assistant1 + user2)
    second_request = mock_llm_server["requests"][1]
    roles = [m["role"] for m in second_request["messages"]]
    assert roles == ["system", "user", "assistant", "user"]


@pytest.mark.asyncio
async def test_group_message_requires_mention(tmp_path: Path, mock_llm_server: dict[str, Any]) -> None:
    """Guild message without @mention is dropped before reaching the agent."""
    adapter = DiscordChannelAdapter(
        channel_id="discord-main", token="fake", dm_scope="per-peer", bot_id=9999
    )
    raw_msg = _make_discord_message(
        bot_id=9999, author_id=42, content="just chatting", is_dm=False
    )
    platform_msg = adapter.normalize_event(raw_msg)
    assert platform_msg is None  # dropped at the channel boundary

    # LLM must never have been called
    assert mock_llm_server["requests"] == []
