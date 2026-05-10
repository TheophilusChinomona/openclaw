"""Tests for the ContextEngine prompt builder."""

from openclaw.context.engine import ContextEngine, ToolDescriptor
from openclaw.models.core import AgentMessage


def make_msg(role: str, content: str) -> AgentMessage:
    return AgentMessage(session_key="k", agent_id="main", role=role, content=content)  # type: ignore[arg-type]


def test_tool_descriptor_to_openai_format():
    td = ToolDescriptor(
        name="search_web",
        description="Search the web",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )
    fmt = td.to_openai_format()
    assert fmt["type"] == "function"
    assert fmt["function"]["name"] == "search_web"
    assert fmt["function"]["description"] == "Search the web"
    assert "query" in fmt["function"]["parameters"]["properties"]


def test_build_messages_no_tools():
    engine = ContextEngine(system_prompt="You are helpful.")
    history = [make_msg("user", "hi"), make_msg("assistant", "hello")]
    result = engine.build_messages(history)
    assert result["messages"][0] == {"role": "system", "content": "You are helpful."}
    assert result["messages"][1] == {"role": "user", "content": "hi"}
    assert result["messages"][2] == {"role": "assistant", "content": "hello"}
    assert result.get("tools") is None


def test_build_messages_with_tools():
    td = ToolDescriptor(
        name="read_file",
        description="Read a file",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    )
    engine = ContextEngine(system_prompt="sys")
    result = engine.build_messages([], tool_descriptors=[td])
    assert len(result["tools"]) == 1
    assert result["tools"][0]["function"]["name"] == "read_file"
    assert result["tool_choice"] == "auto"


def test_build_messages_injects_skill_content():
    engine = ContextEngine(system_prompt="Base prompt.", skill_bodies=["## Skill A\nDo X."])
    result = engine.build_messages([])
    system_content = result["messages"][0]["content"]
    assert "Base prompt." in system_content
    assert "Skill A" in system_content


def test_estimate_tokens():
    engine = ContextEngine(system_prompt="")
    # "hello" → 5 chars → ~1 token
    assert engine.estimate_tokens("hello") >= 1
    # 400-char string → at least 50 tokens
    long_text = "a" * 400
    assert engine.estimate_tokens(long_text) >= 50
