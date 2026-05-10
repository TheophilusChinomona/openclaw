"""Built-in tools: web_search, exec_command, read_file, write_file, search_files."""

from __future__ import annotations

import glob
import subprocess
from pathlib import Path

from openclaw.tools.registry import register_tool


def _search_web(query: str, max_results: int = 5) -> str:
    from duckduckgo_search import DDGS

    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    if not results:
        return "No results found."
    lines = []
    for r in results:
        lines.append(f"**{r.get('title', '')}**\n{r.get('href', '')}\n{r.get('body', '')}")
    return "\n\n".join(lines)


def _exec_command(command: str, timeout: int = 30) -> str:
    try:
        import shlex
        result = subprocess.run(
            shlex.split(command),
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s"
    except Exception as e:
        return f"Error: {e}"


def _read_file(path: str) -> str:
    try:
        return Path(path).expanduser().read_text()
    except Exception as e:
        return f"Error reading file: {e}"


def _write_file(path: str, content: str) -> str:
    try:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Written {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def _search_files(directory: str, pattern: str = "*") -> str:
    try:
        base = Path(directory).expanduser()
        matches = list(base.glob(pattern))
        if not matches:
            return "No files matched."
        return "\n".join(str(m.relative_to(base)) for m in sorted(matches))
    except Exception as e:
        return f"Error searching files: {e}"


_REGISTERED = False


def register_all_builtin_tools() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    _REGISTERED = True

    register_tool(
        "search_web",
        _search_web,
        description="Search the web using DuckDuckGo.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Max results (default 5)"},
            },
            "required": ["query"],
        },
    )
    register_tool(
        "exec_command",
        _exec_command,
        description="Execute a shell command and return its output.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)"},
            },
            "required": ["command"],
        },
    )
    register_tool(
        "read_file",
        _read_file,
        description="Read the contents of a file.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "File path"}},
            "required": ["path"],
        },
    )
    register_tool(
        "write_file",
        _write_file,
        description="Write content to a file.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
    )
    register_tool(
        "search_files",
        _search_files,
        description="Search for files matching a glob pattern in a directory.",
        parameters={
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Directory to search"},
                "pattern": {"type": "string", "description": "Glob pattern (default *)"},
            },
            "required": ["directory"],
        },
    )
