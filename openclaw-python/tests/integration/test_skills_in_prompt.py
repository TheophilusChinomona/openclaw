"""Integration: SKILL.md files on disk flow through SkillsLoader into ContextEngine.

Verifies that skill content from disk ends up verbatim in the assembled LLM
messages, which is the critical path for agents that rely on skill-injected
behaviour.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from openclaw.context.engine import ContextEngine
from openclaw.models.core import AgentMessage
from openclaw.skills.loader import load_skills


RESEARCHER_SKILL = """\
---
name: researcher
description: Deep research with citations
---
## Researcher

Always cite your sources. Prefer peer-reviewed material over blog posts.
When uncertain, say so explicitly.
"""

CODER_SKILL = """\
---
name: coder
description: Write clean, typed Python
---
## Coder

Write idiomatic Python 3.11+. Prefer dataclasses and type annotations.
Never use `assert` for runtime checks.
"""


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    d = tmp_path / "skills"
    d.mkdir()
    (d / "researcher.md").write_text(RESEARCHER_SKILL)
    (d / "coder.md").write_text(CODER_SKILL)
    return d


def test_skill_content_appears_in_system_message(skills_dir: Path) -> None:
    skills = load_skills(skills_dir)
    engine = ContextEngine(
        system_prompt="Base instructions.",
        skill_bodies=[s.body for s in skills],
    )
    result = engine.build_messages([])
    system_content = result["messages"][0]["content"]

    assert "Base instructions." in system_content
    assert "Always cite your sources" in system_content
    assert "idiomatic Python 3.11+" in system_content


def test_only_requested_skills_are_loaded(skills_dir: Path) -> None:
    skills = load_skills(skills_dir, names=["researcher"])
    engine = ContextEngine(
        system_prompt="sys",
        skill_bodies=[s.body for s in skills],
    )
    result = engine.build_messages([])
    system_content = result["messages"][0]["content"]

    assert "Always cite your sources" in system_content
    assert "idiomatic Python" not in system_content  # coder skill excluded


def test_skills_plus_history_plus_tools(skills_dir: Path) -> None:
    """All three prompt sections are assembled in the correct order."""
    from openclaw.context.engine import ToolDescriptor

    skills = load_skills(skills_dir, names=["researcher"])
    engine = ContextEngine(
        system_prompt="You are an agent.",
        skill_bodies=[s.body for s in skills],
    )
    history = [
        AgentMessage(session_key="k", agent_id="main", role="user", content="find papers on LLMs"),
    ]
    tool = ToolDescriptor(
        name="search_web",
        description="Search the web",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    )
    result = engine.build_messages(history, tool_descriptors=[tool])

    messages = result["messages"]
    assert messages[0]["role"] == "system"
    assert "You are an agent." in messages[0]["content"]
    assert "Always cite your sources" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "find papers on LLMs"
    assert result["tools"][0]["function"]["name"] == "search_web"


def test_missing_skills_dir_returns_empty(tmp_path: Path) -> None:
    skills = load_skills(tmp_path / "nonexistent")
    assert skills == []
    engine = ContextEngine(system_prompt="base", skill_bodies=[])
    result = engine.build_messages([])
    assert result["messages"][0]["content"] == "base"
