"""Session manager — per-user JSONL disk store with context windowing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openclaw.models.core import AgentMessage


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return max(1, len(text) // 4)


class SessionManager:
    def __init__(self, store: str = "~/.openclaw/sessions", max_context_tokens: int = 8192) -> None:
        self._root = Path(store).expanduser()
        self._root.mkdir(parents=True, exist_ok=True)
        self._max_tokens = max_context_tokens

    def _session_path(self, session_key: str) -> Path:
        safe = session_key.replace(":", "__")
        return self._root / f"{safe}.jsonl"

    def load(self, session_key: str) -> list[AgentMessage]:
        path = self._session_path(session_key)
        if not path.exists():
            return []
        msgs: list[AgentMessage] = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            data: dict[str, Any] = json.loads(line)
            msgs.append(
                AgentMessage(
                    session_key=data.get("session_key", session_key),
                    agent_id=data.get("agent_id", ""),
                    role=data["role"],  # type: ignore[arg-type]
                    content=data.get("content", ""),
                    tool_calls=data.get("tool_calls", []),
                    tool_results=data.get("tool_results", []),
                )
            )
        return msgs

    def append(self, session_key: str, msg: AgentMessage) -> None:
        path = self._session_path(session_key)
        record = {
            "session_key": msg.session_key,
            "agent_id": msg.agent_id,
            "role": msg.role,
            "content": msg.content,
            "tool_calls": msg.tool_calls,
            "tool_results": msg.tool_results,
        }
        with path.open("a") as f:
            f.write(json.dumps(record) + "\n")

    def prune(self, session_key: str) -> None:
        """Evict oldest turns until total estimated token count is under the budget."""
        msgs = self.load(session_key)
        while msgs:
            total = sum(_estimate_tokens(m.content) for m in msgs)
            if total <= self._max_tokens:
                break
            msgs.pop(0)
        # Rewrite the file
        path = self._session_path(session_key)
        path.write_text(
            "".join(
                json.dumps({
                    "session_key": m.session_key,
                    "agent_id": m.agent_id,
                    "role": m.role,
                    "content": m.content,
                    "tool_calls": m.tool_calls,
                    "tool_results": m.tool_results,
                }) + "\n"
                for m in msgs
            )
        )

    def clear(self, session_key: str) -> None:
        """Reset session (e.g. /new command)."""
        path = self._session_path(session_key)
        if path.exists():
            path.unlink()

    def to_llm_format(self, session_key: str) -> list[dict[str, Any]]:
        """Convert session history to OpenAI messages array format."""
        return [{"role": m.role, "content": m.content} for m in self.load(session_key)]
