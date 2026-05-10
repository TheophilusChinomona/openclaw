"""Tests for DiscordChannelAdapter."""

from unittest.mock import MagicMock

import pytest

from openclaw.channels.discord import DiscordChannelAdapter
from openclaw.models.core import ChatType


def make_adapter() -> DiscordChannelAdapter:
    return DiscordChannelAdapter(
        channel_id="discord-main",
        token="discord-token",
        dm_scope="per-peer",
        bot_id=99999,
    )


def _make_message(is_dm: bool, content: str, author_id: int = 1, channel_id: int = 200,
                  guild_id: int | None = None, thread: bool = False) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    msg.id = 55
    msg.author.id = author_id
    msg.author.bot = False
    if is_dm:
        msg.guild = None
        msg.channel.type = MagicMock()
        msg.channel.type.name = "private"
        msg.channel.id = channel_id
        msg.channel.recipient.id = author_id
    else:
        msg.guild = MagicMock()
        msg.guild.id = guild_id or 777
        msg.channel.id = channel_id
        msg.channel.type = MagicMock()
        msg.channel.type.name = "public_thread" if thread else "text"
        if thread:
            msg.channel.parent_id = channel_id
    return msg


def test_normalize_dm_message():
    adapter = make_adapter()
    msg = _make_message(is_dm=True, content="hello bot")
    result = adapter.normalize_event(msg)
    assert result is not None
    assert result.peer.kind == ChatType.DIRECT
    assert result.text == "hello bot"


def test_normalize_guild_message():
    adapter = make_adapter()
    msg = _make_message(is_dm=False, content="<@99999> help", guild_id=777)
    result = adapter.normalize_event(msg)
    assert result is not None
    assert result.peer.kind == ChatType.GROUP
    assert result.guild_id == "777"


def test_bot_mention_stripped():
    adapter = make_adapter()
    msg = _make_message(is_dm=False, content="<@99999> what time is it?", guild_id=777)
    result = adapter.normalize_event(msg)
    assert result is not None
    assert "<@99999>" not in result.text
    assert "what time is it?" in result.text


def test_guild_message_without_mention_skipped():
    adapter = make_adapter()
    msg = _make_message(is_dm=False, content="just talking", guild_id=777)
    result = adapter.normalize_event(msg)
    assert result is None


def test_bot_own_message_skipped():
    adapter = make_adapter()
    msg = _make_message(is_dm=True, content="I said this")
    msg.author.id = 99999  # same as bot_id
    result = adapter.normalize_event(msg)
    assert result is None


def test_thread_message_has_thread_id():
    adapter = make_adapter()
    msg = _make_message(is_dm=False, content="<@99999> thread reply", guild_id=777, thread=True)
    result = adapter.normalize_event(msg)
    assert result is not None
    assert result.thread_id is not None
