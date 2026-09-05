import json
from typing import Dict, Any, Optional
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END

from app.developer.schemas import DeveloperTaskInput, DeveloperTaskOutput, TaskType, TaskStatus
from app.developer.errors import ErrorTaxonomy
from app.developer.mcp.gateway import MCPGateway
from app.developer.agents.repository import RepositoryAgent
from app.developer.agents.coding import CodingAgent
from app.developer.agents.documentation import DocumentationAgent


# 1. State Definition
class DeveloperState(TypedDict):
    input_payload: DeveloperTaskInput
    trace_id: str
    
    # Internal routing state
    task_type: TaskType
    
    # Agent execution results
    agent_result: Optional[Dict[str, Any]]
    
    # Final normalized output for Member 2
    output_payload: Optional[DeveloperTaskOutput]
    
    # Error tracking
    error: Optional[str]


# 2. Node Implementations
def validate_task_node(state: DeveloperState) -> DeveloperState:
    """Validates the input payload matches the expected schema."""
    try:
        # Re-validate against Pydantic in case it was passed as a dict
        if isinstance(state["input_payload"], dict):
            task_input = DeveloperTaskInput(**state["input_payload"])
        else:
            task_input = state["input_payload"]
            
        return {
            "task_type": task_input.task_type,
            "error": None
        }
    except Exception as e:
        return {
            "task_type": None,
            "error": f"[{ErrorTaxonomy.VALIDATION_INPUT.value}] Invalid Input: {str(e)}"
        }


def route_task(state: DeveloperState) -> str:
    """Conditional routing based on task_type."""
    if state.get("error"):
        return "format_error"
        
    task_type = state.get("task_type")
    if task_type == TaskType.REPO_ANALYSIS:
        return "repository_agent"
    elif task_type == TaskType.CODE_GEN:
        return "coding_agent"
    elif task_type == TaskType.DOC_GEN:
        return "documentation_agent"
    else:
        return "format_error"


# 3. Agent Execution Factories (Curried for injection)
def create_repository_node(mcp_gateway: MCPGateway):
    async def repository_node(state: DeveloperState) -> DeveloperState:
        agent = RepositoryAgent(mcp_gateway)
        try:
            params = state["input_payload"].params if hasattr(state["input_payload"], "params") else state["input_payload"].get("params", {})
            params["repo_ref"] = state["input_payload"].repo_ref if hasattr(state["input_payload"], "repo_ref") else state["input_payload"].get("repo_ref")
            
            result = await agent.execute(params, state.get("trace_id", "N/A"))
            return {"agent_result": result}
        except Exception as e:
            return {"error": str(e)}
    return repository_node


def create_coding_node(mcp_gateway: MCPGateway):
    async def coding_node(state: DeveloperState) -> DeveloperState:
        agent = CodingAgent(mcp_gateway, mode="apply")
        try:
            params = state["input_payload"].params if hasattr(state["input_payload"], "params") else state["input_payload"].get("params", {})
            params["repo_ref"] = state["input_payload"].repo_ref if hasattr(state["input_payload"], "repo_ref") else state["input_payload"].get("repo_ref")
            
            result = await agent.execute(params, state.get("trace_id", "N/A"))
            return {"agent_result": result}
        except Exception as e:
            return {"error": str(e)}
    return coding_node


def create_documentation_node(mcp_gateway: MCPGateway):
    async def documentation_node(state: DeveloperState) -> DeveloperState:
        agent = DocumentationAgent(mcp_gateway, mode="apply")
        try:
            params = state["input_payload"].params if hasattr(state["input_payload"], "params") else state["input_payload"].get("params", {})
            params["repo_ref"] = state["input_payload"].repo_ref if hasattr(state["input_payload"], "repo_ref") else state["input_payload"].get("repo_ref")
            
            result = await agent.execute(params, state.get("trace_id", "N/A"))
            return {"agent_result": result}
        except Exception as e:
            return {"error": str(e)}
    return documentation_node


# 4. Normalization Node
def format_result_node(state: DeveloperState) -> DeveloperState:
    """Formats the agent result into DeveloperTaskOutput."""
    if state.get("error"):
        output = DeveloperTaskOutput(
            result={"error": state["error"]},
            artifacts=[],
            status=TaskStatus.ERROR
        )
        return {"output_payload": output}

    agent_res = state.get("agent_result", {})
    
    # Extract artifacts dynamically based on agent type
    artifacts = []
    task_type = state.get("task_type")
    
    if task_type == TaskType.CODE_GEN:
        artifacts = agent_res.get("files_changed", [])
    elif task_type == TaskType.DOC_GEN:
        if agent_res.get("artifact"):
            artifacts = [agent_res["artifact"]]
            
    output = DeveloperTaskOutput(
        result=agent_res,
        artifacts=artifacts,
        status=TaskStatus.SUCCESS
    )
    return {"output_payload": output}


# 5. Graph Compiler
def compile_developer_subgraph(mcp_gateway: MCPGateway):
    """
    Compiles and returns the isolated Developer Subgraph executable graph.
    """
    graph = StateGraph(DeveloperState)
    
    graph.add_node("validate", validate_task_node)
    graph.add_node("repository_agent", create_repository_node(mcp_gateway))
    graph.add_node("coding_agent", create_coding_node(mcp_gateway))
    graph.add_node("documentation_agent", create_documentation_node(mcp_gateway))
    graph.add_node("format_result", format_result_node)
    graph.add_node("format_error", format_result_node)
    
    graph.add_edge(START, "validate")
    
    graph.add_conditional_edges(
        "validate",
        route_task,
        {
            "repository_agent": "repository_agent",
            "coding_agent": "coding_agent",
            "documentation_agent": "documentation_agent",
            "format_error": "format_error"
        }
    )
    
    graph.add_edge("repository_agent", "format_result")
    graph.add_edge("coding_agent", "format_result")
    graph.add_edge("documentation_agent", "format_result")
    
    graph.add_edge("format_result", END)
    graph.add_edge("format_error", END)
    
    return graph.compile()
