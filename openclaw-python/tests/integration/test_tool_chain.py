"""Integration: AgentLoop executes real file tools and feeds results back.

The mock LLM returns a tool_call on turn 1 and a text response on turn 2.
AgentLoop must execute the real tool, append the result, and call the LLM again.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from openclaw.agent.loop import AgentLoop
from openclaw.context.engine import ContextEngine
from openclaw.session.manager import SessionManager
from openclaw.tools.builtin import register_all_builtin_tools
from openclaw.tools.registry import get_tool


@pytest.fixture(autouse=True)
def _register_tools() -> None:
    register_all_builtin_tools()


@pytest.mark.asyncio
async def test_agent_reads_real_file(tmp_path: Path, mock_llm_server: dict[str, Any]) -> None:
    """Agent calls read_file on a real tmp file; result appears in the second LLM call."""
    target = tmp_path / "data.txt"
    target.write_text("secret content 42")

    mock_llm_server["responses"].extend([
        # Turn 1: LLM asks to read the file
        {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_read",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": json.dumps({"path": str(target)}),
                        },
                    }],
                }
            }]
        },
        # Turn 2: LLM produces final answer after seeing the file content
        {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "The file says: secret content 42",
                    "tool_calls": None,
                }
            }]
        },
    ])

    sm = SessionManager(store=str(tmp_path / "sessions"))
    engine = ContextEngine(system_prompt="You are a file assistant.")
    loop = AgentLoop(
        session_manager=sm,
        context_engine=engine,
        tool_registry={"read_file": get_tool("read_file")["handler"]},
        api_base=mock_llm_server["base_url"],
        api_key="sk-test",
        model="gpt-4o",
    )

    response = await loop.run("agent:main:main", "main", "what is in data.txt?")

    assert response.text == "The file says: secret content 42"
    assert response.tool_calls_made == 1

    # Second LLM call must include the tool result in the message history
    second_request = mock_llm_server["requests"][1]
    roles = [m["role"] for m in second_request["messages"]]
    assert "tool" in roles
    tool_msg = next(m for m in second_request["messages"] if m["role"] == "tool")
    assert "secret content 42" in tool_msg["content"]


@pytest.mark.asyncio
async def test_agent_writes_then_reads_file(tmp_path: Path, mock_llm_server: dict[str, Any]) -> None:
    """Agent writes a file on turn 1 and reads it back on turn 2 (two sequential tool calls)."""
    output_path = str(tmp_path / "output.txt")

    mock_llm_server["responses"].extend([
        # Turn 1: write
        {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_write",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": json.dumps({"path": output_path, "content": "hello world"}),
                        },
                    }],
                }
            }]
        },
        # Turn 2: read it back
        {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_read",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": json.dumps({"path": output_path}),
                        },
                    }],
                }
            }]
        },
        # Turn 3: final answer
        {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Done — wrote and verified.",
                    "tool_calls": None,
                }
            }]
        },
    ])

    sm = SessionManager(store=str(tmp_path / "sessions"))
    engine = ContextEngine(system_prompt="sys")
    loop = AgentLoop(
        session_manager=sm,
        context_engine=engine,
        tool_registry={
            "write_file": get_tool("write_file")["handler"],
            "read_file": get_tool("read_file")["handler"],
        },
        api_base=mock_llm_server["base_url"],
        api_key="sk-test",
        model="gpt-4o",
    )

    response = await loop.run("agent:main:main", "main", "write hello world then read it back")

    assert response.text == "Done — wrote and verified."
    assert response.tool_calls_made == 2
    assert Path(output_path).read_text() == "hello world"
