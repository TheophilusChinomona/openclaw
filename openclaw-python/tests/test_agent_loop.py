"""Tests for AgentLoop — LLM inference + tool-call loop."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openclaw.agent.loop import AgentLoop, MaxIterationsError
from openclaw.context.engine import ContextEngine, ToolDescriptor
from openclaw.session.manager import SessionManager


def make_loop(tmp_path: Path, tool_registry: dict | None = None) -> AgentLoop:
    sm = SessionManager(store=str(tmp_path))
    engine = ContextEngine(system_prompt="You are helpful.")
    return AgentLoop(
        session_manager=sm,
        context_engine=engine,
        tool_registry=tool_registry or {},
        api_base="http://fake-llm/v1",
        api_key="sk-test",
        model="gpt-4o",
    )


@pytest.mark.asyncio
async def test_text_response_no_tools(tmp_path: Path):
    loop = make_loop(tmp_path)
    fake_response = {
        "choices": [{"message": {"role": "assistant", "content": "Hello!", "tool_calls": None}}]
    }
    with patch.object(loop, "_call_llm", new=AsyncMock(return_value=fake_response)):
        result = await loop.run("agent:main:main", "main", "hi")
    assert result.text == "Hello!"
    assert result.tool_calls_made == 0


@pytest.mark.asyncio
async def test_tool_call_then_text(tmp_path: Path):
    def echo_tool(text: str) -> str:
        return f"echoed: {text}"

    loop = make_loop(tmp_path, tool_registry={"echo": echo_tool})

    tool_call_response = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call1",
                    "type": "function",
                    "function": {"name": "echo", "arguments": '{"text": "hello"}'},
                }],
            }
        }]
    }
    text_response = {
        "choices": [{"message": {"role": "assistant", "content": "Done!", "tool_calls": None}}]
    }

    call_count = 0

    async def fake_call_llm(context: dict) -> dict:
        nonlocal call_count
        call_count += 1
        return tool_call_response if call_count == 1 else text_response

    with patch.object(loop, "_call_llm", new=fake_call_llm):
        result = await loop.run("agent:main:main", "main", "call echo")

    assert result.text == "Done!"
    assert result.tool_calls_made == 1


@pytest.mark.asyncio
async def test_max_iterations_raises(tmp_path: Path):
    loop = make_loop(tmp_path)
    # Always return a tool call response → should hit max iterations
    tool_call_response = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call1",
                    "type": "function",
                    "function": {"name": "missing_tool", "arguments": "{}"},
                }],
            }
        }]
    }
    with patch.object(loop, "_call_llm", new=AsyncMock(return_value=tool_call_response)):
        with pytest.raises(MaxIterationsError):
            await loop.run("agent:main:main", "main", "loop forever")
