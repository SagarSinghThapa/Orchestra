import pytest
import os
import asyncio
from pathlib import Path

from app.developer.mcp.servers.filesystem import ReadFileTool, ListFilesTool, SearchFilesTool
from app.developer.mcp.servers.repository import RepoTreeTool, FileMetadataTool, SearchCodeTool
from app.developer.mcp.servers.git import GitStatusTool


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    
    # Create some files
    (root / "main.py").write_text("print('hello world')", encoding="utf-8")
    (root / "utils.py").write_text("def helper():\n    pass", encoding="utf-8")
    
    subdir = root / "src"
    subdir.mkdir()
    (subdir / "app.py").write_text("import sys\n# hello", encoding="utf-8")
    
    return str(root)


@pytest.mark.asyncio
async def test_read_file_tool(workspace):
    tool = ReadFileTool(workspace)
    content = await tool.execute({"path": "main.py"}, "trace-1")
    assert content == "print('hello world')"


@pytest.mark.asyncio
async def test_list_files_tool(workspace):
    tool = ListFilesTool(workspace)
    files = await tool.execute({"path": ""}, "trace-1")
    names = [f["name"] for f in files]
    assert "main.py" in names
    assert "src" in names


@pytest.mark.asyncio
async def test_search_files_tool(workspace):
    tool = SearchFilesTool(workspace)
    # Searching for files containing "main" in name
    matches = await tool.execute({"pattern": "main"}, "trace-1")
    assert "main.py" in matches


@pytest.mark.asyncio
async def test_search_code_tool(workspace):
    tool = SearchCodeTool(workspace)
    results = await tool.execute({"pattern": "hello"}, "trace-1")
    
    # "hello" is in main.py and src/app.py
    files = [r["file"] for r in results]
    assert "main.py" in files
    # Normalize paths for cross-platform assert
    assert any("app.py" in f for f in files)


@pytest.mark.asyncio
async def test_git_status_no_repo(workspace):
    tool = GitStatusTool(workspace)
    with pytest.raises(Exception):
        await tool.execute({}, "trace-1")

