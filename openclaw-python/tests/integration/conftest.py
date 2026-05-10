"""Shared fixtures for integration tests.

Key fixture: `mock_llm_server` — a real aiohttp test server that mimics the
OpenAI /chat/completions endpoint. AgentLoop makes genuine HTTP calls to it,
so we exercise the full network path without hitting real APIs.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer


@pytest.fixture
async def mock_llm_server(aiohttp_server: Any) -> AsyncIterator[dict[str, Any]]:
    """Spin up a local OpenAI-compatible chat/completions endpoint.

    Callers can prime `responses` with a list of dicts; the server pops and
    returns them in order (FIFO).  After the list is exhausted it returns a
    generic text reply so tests don't crash on unexpected calls.
    """
    state: dict[str, Any] = {"responses": [], "requests": []}

    async def completions(request: web.Request) -> web.Response:
        body = await request.json()
        state["requests"].append(body)
        if state["responses"]:
            reply = state["responses"].pop(0)
        else:
            reply = {
                "choices": [
                    {"message": {"role": "assistant", "content": "(default mock)", "tool_calls": None}}
                ]
            }
        return web.json_response(reply)

    app = web.Application()
    app.router.add_post("/chat/completions", completions)
    server: TestServer = await aiohttp_server(app)
    state["base_url"] = f"http://{server.host}:{server.port}"
    yield state
