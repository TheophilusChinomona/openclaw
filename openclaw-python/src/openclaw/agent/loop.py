"""AgentLoop — LLM inference + tool-call loop with MAX_TOOL_ITERATIONS guard."""

from __future__ import annotations

import json
from typing import Any, Callable

import httpx

from openclaw.context.engine import ContextEngine
from openclaw.models.core import AgentMessage, AgentResponse
from openclaw.session.manager import SessionManager

MAX_TOOL_ITERATIONS = 10


class MaxIterationsError(RuntimeError):
    """Raised when the agent loop exceeds MAX_TOOL_ITERATIONS without a text response."""


class AgentLoop:
    def __init__(
        self,
        session_manager: SessionManager,
        context_engine: ContextEngine,
        tool_registry: dict[str, Callable[..., Any]],
        api_base: str = "https://api.openai.com/v1",
        api_key: str = "",
        model: str = "gpt-4o",
    ) -> None:
        self._sm = session_manager
        self._engine = context_engine
        self._tools = tool_registry
        self._api_base = api_base.rstrip("/")
        self._api_key = api_key
        self._model = model

    async def run(self, session_key: str, agent_id: str, user_text: str) -> AgentResponse:
        user_msg = AgentMessage(
            session_key=session_key,
            agent_id=agent_id,
            role="user",
            content=user_text,
        )
        self._sm.append(session_key, user_msg)

        tool_calls_made = 0

        for _ in range(MAX_TOOL_ITERATIONS):
            history = self._sm.load(session_key)
            context = self._engine.build_messages(history)
            response = await self._call_llm(context)

            choice = response["choices"][0]["message"]
            tool_calls = choice.get("tool_calls") or []

            if not tool_calls:
                text = choice.get("content") or ""
                assistant_msg = AgentMessage(
                    session_key=session_key,
                    agent_id=agent_id,
                    role="assistant",
                    content=text,
                )
                self._sm.append(session_key, assistant_msg)
                return AgentResponse(
                    text=text,
                    session_key=session_key,
                    agent_id=agent_id,
                    tool_calls_made=tool_calls_made,
                )

            # Execute each tool call and record results
            for tc in tool_calls:
                fn_name = tc["function"]["name"]
                fn_args_raw = tc["function"].get("arguments", "{}")
                try:
                    fn_args: dict[str, Any] = json.loads(fn_args_raw)
                except json.JSONDecodeError:
                    fn_args = {}

                result = await self._execute_tool(fn_name, fn_args)
                tool_calls_made += 1

                tool_result_msg = AgentMessage(
                    session_key=session_key,
                    agent_id=agent_id,
                    role="tool",
                    content=str(result),
                )
                self._sm.append(session_key, tool_result_msg)

        raise MaxIterationsError(
            f"Agent loop exceeded {MAX_TOOL_ITERATIONS} tool iterations without a text response."
        )

    async def _call_llm(self, context: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": self._model, "messages": context["messages"]}
        if "tools" in context:
            payload["tools"] = context["tools"]
            payload["tool_choice"] = context.get("tool_choice", "auto")

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._api_base}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]

    async def _execute_tool(self, name: str, args: dict[str, Any]) -> Any:
        handler = self._tools.get(name)
        if handler is None:
            return f"Error: tool '{name}' not found"
        import asyncio
        if asyncio.iscoroutinefunction(handler):
            return await handler(**args)
        return handler(**args)
