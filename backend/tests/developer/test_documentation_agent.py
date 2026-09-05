import pytest
from pathlib import Path

from app.developer.mcp.gateway import MCPGateway
from app.developer.mcp.servers.filesystem import WriteFileTool
from app.developer.agents.documentation import DocumentationAgent


@pytest.fixture
def doc_workspace(tmp_path):
    root = tmp_path / "test_docs"
    root.mkdir()
    return str(root)


@pytest.fixture
def dummy_repo_context():
    return {
        "repository": {"tree_size": 10},
        "languages": ["Python", "TypeScript"],
        "frameworks": ["FastAPI"],
        "important_files": ["package.json", "main.py"],
        "dependencies": ["pydantic", "react"],
        "entry_points": ["main.py"]
    }


@pytest.mark.asyncio
async def test_doc_agent_preview(doc_workspace, dummy_repo_context):
    gateway = MCPGateway()
    gateway.register_tool(WriteFileTool(doc_workspace))
    
    agent = DocumentationAgent(mcp_gateway=gateway, mode="preview")
    
    params = {
        "doc_type": "README",
        "repository_context": dummy_repo_context,
        "output_path": "README.md"
    }
    
    result = await agent.execute(params, "trace-doc-1")
    
    # Assert deterministic extraction
    assert "README" in result["content"]
    assert "Python, TypeScript" in result["content"]
    assert "pydantic, react" in result["content"]
    assert "main.py" in result["content"]
    
    # Check that it didn't actually write
    output_file = Path(doc_workspace) / "README.md"
    assert not output_file.exists()
    assert result["artifact"] is None


@pytest.mark.asyncio
async def test_doc_agent_apply(doc_workspace, dummy_repo_context):
    gateway = MCPGateway()
    gateway.register_tool(WriteFileTool(doc_workspace))
    
    agent = DocumentationAgent(mcp_gateway=gateway, mode="apply")
    
    params = {
        "doc_type": "architecture",
        "repository_context": {"architecture": {"inferred": "Microservices"}},
        "output_path": "docs/architecture.md"
    }
    
    result = await agent.execute(params, "trace-doc-2")
    
    assert "Architecture" in result["content"]
    assert "Microservices" in result["content"]
    
    # Check that it actually wrote
    output_file = Path(doc_workspace) / "docs" / "architecture.md"
    assert output_file.exists()
    assert "Microservices" in output_file.read_text(encoding="utf-8")
    assert result["artifact"] == "docs/architecture.md"


@pytest.mark.asyncio
async def test_doc_agent_missing_context(doc_workspace):
    gateway = MCPGateway()
    gateway.register_tool(WriteFileTool(doc_workspace))
    
    agent = DocumentationAgent(mcp_gateway=gateway, mode="preview")
    
    params = {
        "doc_type": "README",
        "repository_context": {},
        "output_path": "README.md"
    }
    
    result = await agent.execute(params, "trace-doc-3")
    
    # Assert anti-hallucination fallback to 'Unknown'
    assert "Unknown" in result["content"]
    assert any("No verified repository context provided" in w for w in result["warnings"])
