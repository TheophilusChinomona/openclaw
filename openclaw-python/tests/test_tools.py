"""Tests for tool registry and built-in tools."""

from pathlib import Path
from unittest.mock import patch

import pytest

from openclaw.tools.registry import get_tool, list_tools, register_tool


def test_register_and_get_tool():
    def my_tool(x: str) -> str:
        return x.upper()

    register_tool("my_tool", my_tool, description="Upcases text",
                  parameters={"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]})
    retrieved = get_tool("my_tool")
    assert retrieved is not None
    assert retrieved["handler"]("hello") == "HELLO"
    assert retrieved["description"] == "Upcases text"


def test_list_tools_returns_names():
    names = list_tools()
    assert isinstance(names, list)


def test_builtin_tools_registered():
    from openclaw.tools.builtin import register_all_builtin_tools
    register_all_builtin_tools()
    names = list_tools()
    for expected in ["read_file", "write_file", "search_files", "exec_command", "search_web"]:
        assert expected in names


def test_read_file(tmp_path: Path):
    from openclaw.tools.registry import get_tool
    from openclaw.tools.builtin import register_all_builtin_tools
    register_all_builtin_tools()

    target = tmp_path / "hello.txt"
    target.write_text("file content here")
    handler = get_tool("read_file")["handler"]
    result = handler(path=str(target))
    assert "file content here" in result


def test_write_file(tmp_path: Path):
    from openclaw.tools.registry import get_tool
    from openclaw.tools.builtin import register_all_builtin_tools
    register_all_builtin_tools()

    target = tmp_path / "out.txt"
    handler = get_tool("write_file")["handler"]
    handler(path=str(target), content="written!")
    assert target.read_text() == "written!"


def test_search_files(tmp_path: Path):
    from openclaw.tools.registry import get_tool
    from openclaw.tools.builtin import register_all_builtin_tools
    register_all_builtin_tools()

    (tmp_path / "a.py").write_text("pass")
    (tmp_path / "b.txt").write_text("hello")
    handler = get_tool("search_files")["handler"]
    result = handler(directory=str(tmp_path), pattern="*.py")
    assert "a.py" in result


def test_exec_command():
    from openclaw.tools.registry import get_tool
    from openclaw.tools.builtin import register_all_builtin_tools
    register_all_builtin_tools()

    handler = get_tool("exec_command")["handler"]
    result = handler(command="echo hello")
    assert "hello" in result


def test_search_web_mocked():
    from openclaw.tools.registry import get_tool
    from openclaw.tools.builtin import register_all_builtin_tools
    register_all_builtin_tools()

    handler = get_tool("search_web")["handler"]
    fake_results = [{"title": "Example", "href": "https://example.com", "body": "An example page."}]
    with patch("duckduckgo_search.DDGS") as mock_ddgs:
        mock_ddgs.return_value.__enter__.return_value.text.return_value = fake_results
        result = handler(query="example")
    assert "Example" in result
