"""ContextEngine — assembles LLM prompt from system prompt, skills, history, and tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openclaw.models.core import AgentMessage


@dataclass
class ToolDescriptor:
    name: str
    description: str
    parameters: dict[str, Any]

    def to_openai_format(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ContextEngine:
    system_prompt: str = ""
    skill_bodies: list[str] = field(default_factory=list)

    def _build_system_content(self) -> str:
        parts = [self.system_prompt] if self.system_prompt else []
        parts.extend(self.skill_bodies)
        return "\n\n".join(parts)

    def build_messages(
        self,
        history: list[AgentMessage],
        tool_descriptors: list[ToolDescriptor] | None = None,
    ) -> dict[str, Any]:
        system_content = self._build_system_content()
        messages: list[dict[str, Any]] = []

        if system_content:
            messages.append({"role": "system", "content": system_content})

        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        result: dict[str, Any] = {"messages": messages}

        if tool_descriptors:
            result["tools"] = [td.to_openai_format() for td in tool_descriptors]
            result["tool_choice"] = "auto"

        return result

    def estimate_tokens(self, text: str) -> int:
        """Rough estimate: ~4 chars per token."""
        return max(1, len(text) // 4)
