import pytest
import os
from pathlib import Path

from app.developer.mcp.gateway import MCPGateway
from app.developer.mcp.servers.filesystem import ReadFileTool, WriteFileTool
from app.developer.agents.coding import CodingAgent


@pytest.fixture
def coding_workspace(tmp_path):
    root = tmp_path / "test_repo"
    root.mkdir()
    
    (root / "main.py").write_text("print('hello world')", encoding="utf-8")
    
    return str(root)


@pytest.mark.asyncio
async def test_coding_agent_preview_mode(coding_workspace):
    gateway = MCPGateway()
    gateway.register_tool(ReadFileTool(coding_workspace))
    gateway.register_tool(WriteFileTool(coding_workspace))
    
    agent = CodingAgent(mcp_gateway=gateway, mode="preview")
    
    params = {
        "repo_ref": "",
        "proposed_changes": {
            "main.py": "print('hello universe')\n",
            "new_file.py": "def test():\n    pass\n"
        }
    }
    
    result = await agent.execute(params, "trace-coding-1")
    
    assert "(Preview mode only)" in result["summary"]
    assert "main.py" in result["files_changed"]
    assert "new_file.py" in result["files_changed"]
    assert "hello universe" in result["diffs"]["main.py"]
    
    # Check that it didn't actually write
    content = Path(coding_workspace, "main.py").read_text(encoding="utf-8")
    assert "hello world" in content


@pytest.mark.asyncio
async def test_coding_agent_apply_mode(coding_workspace):
    gateway = MCPGateway()
    gateway.register_tool(ReadFileTool(coding_workspace))
    gateway.register_tool(WriteFileTool(coding_workspace))
    
    agent = CodingAgent(mcp_gateway=gateway, mode="apply")
    
    params = {
        "repo_ref": "",
        "proposed_changes": {
            "main.py": "print('hello universe')\n"
        }
    }
    
    result = await agent.execute(params, "trace-coding-2")
    
    assert "Successfully applied changes" in result["summary"]
    
    # Check that it actually wrote
    content = Path(coding_workspace, "main.py").read_text(encoding="utf-8")
    assert content == "print('hello universe')\n"


@pytest.mark.asyncio
async def test_coding_agent_invalid_syntax(coding_workspace):
    gateway = MCPGateway()
    gateway.register_tool(ReadFileTool(coding_workspace))
    gateway.register_tool(WriteFileTool(coding_workspace))
    
    agent = CodingAgent(mcp_gateway=gateway, mode="apply")
    
    params = {
        "repo_ref": "",
        "proposed_changes": {
            "main.py": "def broken(\n"
        }
    }
    
    result = await agent.execute(params, "trace-coding-3")
    
    # Should abort apply
    assert "Apply aborted due to validation failures" in result["summary"]
    assert any("Validation failed" in w for w in result["warnings"])
    assert "SyntaxError" in result["validation"]["main.py"]
    
    # Original should be untouched
    content = Path(coding_workspace, "main.py").read_text(encoding="utf-8")
    assert content == "print('hello world')"


@pytest.mark.asyncio
async def test_coding_agent_excessive_changes(coding_workspace):
    gateway = MCPGateway()
    agent = CodingAgent(mcp_gateway=gateway, mode="apply", max_files_changed=1)
    
    params = {
        "repo_ref": "",
        "proposed_changes": {
            "main.py": "1",
            "second.py": "2"
        }
    }
    
    result = await agent.execute(params, "trace-coding-4")
    
    assert "Failed due to max files limit" in result["summary"]
    assert "exceed max allowed" in result["warnings"][0]


@pytest.mark.asyncio
async def test_coding_agent_path_traversal(coding_workspace):
    gateway = MCPGateway()
    gateway.register_tool(ReadFileTool(coding_workspace))
    gateway.register_tool(WriteFileTool(coding_workspace))
    
    agent = CodingAgent(mcp_gateway=gateway, mode="apply")
    
    params = {
        "repo_ref": "",
        "proposed_changes": {
            "../outside.py": "print('hacked')"
        }
    }
    
    result = await agent.execute(params, "trace-coding-5")
    
    # WriteFileTool fails due to sandbox ValidationError(E1xx)
    assert any("Failed to write ../outside.py" in w for w in result["warnings"])
