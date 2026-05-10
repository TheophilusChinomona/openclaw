"""Tests for SessionManager — disk persistence and context windowing."""

from pathlib import Path

import pytest

from openclaw.models.core import AgentMessage
from openclaw.session.manager import SessionManager

SESSION_KEY = "agent:main:direct:123"


def make_msg(role: str, content: str) -> AgentMessage:
    return AgentMessage(
        session_key=SESSION_KEY,
        agent_id="main",
        role=role,  # type: ignore[arg-type]
        content=content,
    )


def test_load_empty_session(tmp_path: Path):
    sm = SessionManager(store=str(tmp_path))
    msgs = sm.load(SESSION_KEY)
    assert msgs == []


def test_append_and_load(tmp_path: Path):
    sm = SessionManager(store=str(tmp_path))
    sm.append(SESSION_KEY, make_msg("user", "hello"))
    sm.append(SESSION_KEY, make_msg("assistant", "hi!"))
    msgs = sm.load(SESSION_KEY)
    assert len(msgs) == 2
    assert msgs[0].role == "user"
    assert msgs[0].content == "hello"
    assert msgs[1].role == "assistant"


def test_jsonl_round_trip(tmp_path: Path):
    sm = SessionManager(store=str(tmp_path))
    sm.append(SESSION_KEY, make_msg("user", "first"))
    # Re-create manager to verify disk persistence
    sm2 = SessionManager(store=str(tmp_path))
    msgs = sm2.load(SESSION_KEY)
    assert len(msgs) == 1
    assert msgs[0].content == "first"


def test_session_path_replaces_colons(tmp_path: Path):
    sm = SessionManager(store=str(tmp_path))
    p = sm._session_path(SESSION_KEY)
    assert ":" not in p.name
    assert p.suffix == ".jsonl"


def test_prune_evicts_oldest(tmp_path: Path):
    # max_context_tokens=50 → very small budget; 10 messages of ~20 chars each should prune
    sm = SessionManager(store=str(tmp_path), max_context_tokens=50)
    for i in range(10):
        sm.append(SESSION_KEY, make_msg("user", f"message number {i} with some extra text here"))
    sm.prune(SESSION_KEY)
    msgs = sm.load(SESSION_KEY)
    # Should have pruned some; remaining count must be less than 10
    assert len(msgs) < 10


def test_clear_session(tmp_path: Path):
    sm = SessionManager(store=str(tmp_path))
    sm.append(SESSION_KEY, make_msg("user", "to be cleared"))
    sm.clear(SESSION_KEY)
    assert sm.load(SESSION_KEY) == []


def test_to_llm_format(tmp_path: Path):
    sm = SessionManager(store=str(tmp_path))
    sm.append(SESSION_KEY, make_msg("user", "q"))
    sm.append(SESSION_KEY, make_msg("assistant", "a"))
    llm_msgs = sm.to_llm_format(SESSION_KEY)
    assert llm_msgs == [
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": "a"},
    ]
