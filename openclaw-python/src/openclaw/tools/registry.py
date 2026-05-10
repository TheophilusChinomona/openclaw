"""Tool registry — central store for all callable tools."""

from __future__ import annotations

from typing import Any, Callable

_REGISTRY: dict[str, dict[str, Any]] = {}


def register_tool(
    name: str,
    handler: Callable[..., Any],
    *,
    description: str = "",
    parameters: dict[str, Any] | None = None,
) -> None:
    _REGISTRY[name] = {
        "handler": handler,
        "description": description,
        "parameters": parameters or {"type": "object", "properties": {}},
    }


def get_tool(name: str) -> dict[str, Any] | None:
    return _REGISTRY.get(name)


def list_tools() -> list[str]:
    return list(_REGISTRY.keys())


def build_tool_descriptors() -> list[dict[str, Any]]:
    """Return all registered tools in OpenAI function-tool format."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": entry["description"],
                "parameters": entry["parameters"],
            },
        }
        for name, entry in _REGISTRY.items()
    ]
