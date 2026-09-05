import pytest
import os
from pathlib import Path

from app.developer.mcp.gateway import MCPGateway
from app.developer.mcp.servers.repository import RepoTreeTool, FileMetadataTool
from app.developer.mcp.servers.filesystem import ReadFileTool, SearchFilesTool
from app.developer.agents.repository import RepositoryAgent


@pytest.fixture
def repo_workspace(tmp_path):
    root = tmp_path / "test_repo"
    root.mkdir()
    
    (root / "package.json").write_text('{"name": "test", "dependencies": {"react": "18.0"}}')
    (root / "main.py").write_text("import os")
    
    src = root / "src"
    src.mkdir()
    (src / "app.py").write_text("from fastapi import FastAPI\napp = FastAPI()")
    
    return str(root)


@pytest.mark.asyncio
async def test_repository_agent_execution(repo_workspace):
    gateway = MCPGateway()
    gateway.register_tool(RepoTreeTool(repo_workspace))
    gateway.register_tool(FileMetadataTool(repo_workspace))
    gateway.register_tool(ReadFileTool(repo_workspace))
    gateway.register_tool(SearchFilesTool(repo_workspace))
    
    agent = RepositoryAgent(mcp_gateway=gateway)
    
    result = await agent.execute({"repo_ref": ""}, "trace-repo-1")
    
    # Assert deterministic extraction and heuristic evaluation
    assert "Python" in result["languages"]
    assert "JavaScript/TypeScript" in result["languages"]
    assert "FastAPI" in result["frameworks"]
    assert "package.json" in result["important_files"]
    assert "main.py" in result["entry_points"]
