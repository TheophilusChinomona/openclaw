"""Tests for session key builders — must match TypeScript behavior exactly."""

import pytest

from openclaw.routing.session_key import (
    DEFAULT_ACCOUNT_ID,
    DEFAULT_AGENT_ID,
    DEFAULT_MAIN_KEY,
    build_agent_main_session_key,
    build_agent_peer_session_key,
    normalize_agent_id,
    normalize_account_id,
    resolve_thread_session_key,
)


def test_defaults():
    assert DEFAULT_AGENT_ID == "main"
    assert DEFAULT_MAIN_KEY == "main"
    assert DEFAULT_ACCOUNT_ID == "default"


def test_main_session_key():
    assert build_agent_main_session_key("main") == "agent:main:main"
    assert build_agent_main_session_key("mybot") == "agent:mybot:main"


def test_dm_scope_main():
    key = build_agent_peer_session_key("main", "telegram-main", "direct", "123", dm_scope="main")
    assert key == "agent:main:main"


def test_dm_scope_per_peer():
    key = build_agent_peer_session_key("main", "telegram-main", "direct", "456", dm_scope="per-peer")
    assert key == "agent:main:direct:456"


def test_dm_scope_per_channel_peer():
    key = build_agent_peer_session_key(
        "main", "telegram-main", "direct", "789", dm_scope="per-channel-peer"
    )
    assert key == "agent:main:telegram-main:direct:789"


def test_dm_scope_per_account_channel_peer():
    key = build_agent_peer_session_key(
        "main",
        "discord-main",
        "direct",
        "999",
        account_id="bot1",
        dm_scope="per-account-channel-peer",
    )
    assert key == "agent:main:discord-main:bot1:direct:999"


def test_per_account_channel_peer_missing_peer_id_falls_back_to_main():
    key = build_agent_peer_session_key(
        "main", "discord-main", "direct", None, account_id="bot1", dm_scope="per-account-channel-peer"
    )
    assert key == "agent:main:main"


def test_group_peer():
    key = build_agent_peer_session_key("main", "telegram-main", "group", "chat100")
    assert key == "agent:main:telegram-main:group:chat100"


def test_thread_suffix():
    base = "agent:main:telegram-main:group:chat100"
    assert resolve_thread_session_key(base, "thread42") == f"{base}:thread:thread42"
    assert resolve_thread_session_key(base, None) == base
    assert resolve_thread_session_key(base, "  ") == base


def test_normalize_agent_id():
    assert normalize_agent_id("Main") == "main"
    assert normalize_agent_id(None) == "main"
    assert normalize_agent_id("") == "main"
    assert normalize_agent_id("my-bot_1") == "my-bot_1"


def test_normalize_account_id():
    assert normalize_account_id(None) == DEFAULT_ACCOUNT_ID
    assert normalize_account_id("") == DEFAULT_ACCOUNT_ID
    assert normalize_account_id("Bot1") == "bot1"
