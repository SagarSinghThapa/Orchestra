import pytest
from app.developer.schemas import DeveloperTaskInput, TaskType, TaskStatus
from app.developer.mcp.gateway import MCPGateway
from app.developer.graph.graph import compile_developer_subgraph

@pytest.fixture
def mcp_gateway():
    # A mock MCP Gateway with no tools registered for isolated graph testing.
    # We only care about routing and normalizations here.
    return MCPGateway()

@pytest.fixture
def developer_subgraph(mcp_gateway):
    return compile_developer_subgraph(mcp_gateway)

@pytest.mark.asyncio
async def test_graph_validation_error(developer_subgraph):
    # Invalid payload (missing task_type)
    result = await developer_subgraph.ainvoke({
        "input_payload": {},
        "trace_id": "test-val-1"
    })
    
    output = result["output_payload"]
    assert output.status == TaskStatus.ERROR
    assert "E1xx" in output.result["error"]

@pytest.mark.asyncio
async def test_graph_repo_analysis_route(developer_subgraph):
    # Route: Repo Analysis
    result = await developer_subgraph.ainvoke({
        "input_payload": {
            "task_type": "repo_analysis",
            "repo_ref": "",
            "params": {}
        },
        "trace_id": "test-repo-1"
    })
    
    output = result["output_payload"]
    assert output.status == TaskStatus.SUCCESS
    # We expect empty repo analysis as no tools are mounted
    assert "languages" in output.result
    assert "recommendations" in output.result

@pytest.mark.asyncio
async def test_graph_code_gen_route(developer_subgraph):
    # Route: Code Gen
    result = await developer_subgraph.ainvoke({
        "input_payload": {
            "task_type": "code_gen",
            "repo_ref": "",
            "params": {
                "proposed_changes": {"test.py": "print('ok')"}
            }
        },
        "trace_id": "test-code-1"
    })
    
    output = result["output_payload"]
    assert output.status == TaskStatus.SUCCESS
    assert output.result["files_changed"] == ["test.py"]
    # Verify artifact extraction matches files_changed for code_gen
    assert output.artifacts == ["test.py"]

@pytest.mark.asyncio
async def test_graph_doc_gen_route(developer_subgraph):
    # Route: Doc Gen
    result = await developer_subgraph.ainvoke({
        "input_payload": {
            "task_type": "doc_gen",
            "repo_ref": "",
            "params": {
                "doc_type": "README",
                "repository_context": {},
                "output_path": "README.md"
            }
        },
        "trace_id": "test-doc-1"
    })
    
    output = result["output_payload"]
    assert output.status == TaskStatus.SUCCESS
    # Artifact generation skipped since mode is "preview" (Wait, coding_node and doc_node factory sets mode="apply")
    # Actually wait: The write tool will fail since it is not registered on this mock gateway!
    # Wait, the coding agent and doc agent will log an error in _call_tool but won't crash!
    # Let's see what happens.
    
    assert output.result["document_type"] == "README"
