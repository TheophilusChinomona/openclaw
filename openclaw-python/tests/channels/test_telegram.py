"""Tests for TelegramChannelAdapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openclaw.channels.telegram import TelegramChannelAdapter
from openclaw.models.core import ChatType


def make_adapter(dm_scope: str = "main") -> TelegramChannelAdapter:
    return TelegramChannelAdapter(
        channel_id="telegram-main",
        token="123:abc",
        dm_scope=dm_scope,
        bot_username="testbot",
    )


def _make_update(chat_type: str, text: str, from_id: int = 1, chat_id: int = 100) -> MagicMock:
    update = MagicMock()
    update.message.text = text
    update.message.message_id = 42
    update.message.from_user.id = from_id
    update.message.chat.id = chat_id
    update.message.chat.type = chat_type  # "private" | "group" | "supergroup"
    update.message.reply_to_message = None
    return update


def test_normalize_dm_returns_direct_peer():
    adapter = make_adapter()
    update = _make_update("private", "hello")
    msg = adapter.normalize_event(update)
    assert msg is not None
    assert msg.peer.kind == ChatType.DIRECT
    assert msg.peer.id == "1"
    assert msg.text == "hello"
    assert msg.channel == "telegram-main"


def test_normalize_group_returns_group_peer():
    adapter = make_adapter()
    update = _make_update("group", "hi @testbot", chat_id=-200)
    msg = adapter.normalize_event(update)
    assert msg is not None
    assert msg.peer.kind == ChatType.GROUP
    assert msg.peer.id == "-200"


def test_group_without_mention_skipped():
    adapter = make_adapter()
    update = _make_update("group", "just chatting without mention", chat_id=-200)
    # In groups, messages without @mention should be skipped (returns None)
    msg = adapter.normalize_event(update)
    assert msg is None


def test_mention_stripped_from_text():
    adapter = make_adapter()
    update = _make_update("group", "@testbot do something", chat_id=-200)
    msg = adapter.normalize_event(update)
    assert msg is not None
    assert "@testbot" not in msg.text
    assert "do something" in msg.text


def test_none_for_missing_text():
    adapter = make_adapter()
    update = MagicMock()
    update.message = None
    assert adapter.normalize_event(update) is None


def test_channel_id_attribute():
    adapter = make_adapter()
    assert adapter.channel_id == "telegram-main"
