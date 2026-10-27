import json
from typing import Dict, Any, Optional, List, Union
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END

from app.developer.schemas import (
    DeveloperTaskInput,
    DeveloperTaskOutput,
    DeveloperRequest,
    DeveloperResponse,
    DeveloperMode,
    ProposedPatch,
    TaskType,
    TaskStatus,
)
from app.developer.errors import ErrorTaxonomy, DeveloperBaseException
from app.developer.mcp.gateway import MCPGateway
from app.developer.logging import scrub_secrets
from app.developer.agents.repository import RepositoryAgent
from app.developer.agents.coding import CodingAgent
from app.developer.agents.documentation import DocumentationAgent
from app.research.llm.base import LLMProvider
from app.research.llm.provider import get_llm_provider


# 1. State Definition
class DeveloperState(TypedDict, total=False):
    input_payload: Any
    trace_id: str

    # Internal routing state
    task_type: Optional[TaskType]

    # Agent execution results
    agent_result: Optional[Dict[str, Any]]

    # Output payloads
    output_payload: Optional[Any]
    developer_response: Optional[DeveloperResponse]

    # Error tracking
    error: Optional[str]

    # Execution budgets & context
    llm_calls_made: int
    tool_calls_made: int
    files_read_count: int
    workspace_root: str
    mode: str
    prompt: str
    target_files: Optional[List[str]]
    expected_file_hashes: Optional[Dict[str, str]]
    context_hints: Optional[Dict[str, str]]
    params: Optional[Dict[str, Any]]
    proposed_changes: Optional[Dict[str, str]]


# 2. Node Implementations
def validate_task_node(state: DeveloperState) -> DeveloperState:
    """Validates the input payload matches DeveloperRequest or DeveloperTaskInput."""
    try:
        raw_input = state["input_payload"]
        if isinstance(raw_input, DeveloperRequest):
            task_type = raw_input.task_type
            mode = raw_input.mode.value if hasattr(raw_input.mode, "value") else str(raw_input.mode)
            prompt = raw_input.prompt
            target_files = raw_input.target_files
            expected_file_hashes = raw_input.expected_file_hashes
            context_hints = raw_input.context_hints
        elif isinstance(raw_input, dict) and "prompt" in raw_input and "task_type" in raw_input:
            validated = DeveloperRequest(**raw_input)
            task_type = validated.task_type
            mode = validated.mode.value if hasattr(validated.mode, "value") else str(validated.mode)
            prompt = validated.prompt
            target_files = validated.target_files
            expected_file_hashes = validated.expected_file_hashes
            context_hints = validated.context_hints
        elif isinstance(raw_input, DeveloperTaskInput):
            task_type = raw_input.task_type
            params = raw_input.params or {}
            mode = params.get("mode", "preview")
            prompt = params.get("prompt", "")
            target_files = params.get("target_files")
            expected_file_hashes = params.get("expected_file_hashes")
            context_hints = params.get("context_hints")
        elif isinstance(raw_input, dict):
            task_input = DeveloperTaskInput(**raw_input)
            task_type = task_input.task_type
            params = task_input.params or {}
            mode = params.get("mode", "preview")
            prompt = params.get("prompt", "")
            target_files = params.get("target_files")
            expected_file_hashes = params.get("expected_file_hashes")
            context_hints = params.get("context_hints")
        else:
            raise ValueError(f"Unrecognized payload type: {type(raw_input)}")

        return {
            "task_type": task_type,
            "mode": mode,
            "prompt": prompt,
            "target_files": target_files,
            "expected_file_hashes": expected_file_hashes,
            "context_hints": context_hints,
            "params": state.get("params"),
            "proposed_changes": state.get("proposed_changes"),
            "llm_calls_made": state.get("llm_calls_made", 0),
            "tool_calls_made": state.get("tool_calls_made", 0),
            "files_read_count": state.get("files_read_count", 0),
            "workspace_root": state.get("workspace_root", ""),
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
def _extract_agent_params(state: DeveloperState) -> Dict[str, Any]:
    raw_payload = state.get("input_payload", {})
    if hasattr(raw_payload, "params"):
        params = dict(raw_payload.params or {})
    elif isinstance(raw_payload, dict):
        params = dict(raw_payload.get("params", {}) or {})
    else:
        params = {}

    # Merge any state params or proposed changes
    if state.get("params") and isinstance(state["params"], dict):
        params.update(state["params"])
    if state.get("proposed_changes"):
        params["proposed_changes"] = state["proposed_changes"]

    if state.get("mode"):
        params["mode"] = state["mode"]
    if state.get("prompt"):
        params["prompt"] = state["prompt"]
    if state.get("target_files") is not None:
        params["target_files"] = state["target_files"]
    if state.get("expected_file_hashes") is not None:
        params["expected_file_hashes"] = state["expected_file_hashes"]
    if state.get("context_hints") is not None:
        params["context_hints"] = state["context_hints"]
    if hasattr(raw_payload, "repo_ref"):
        params["repo_ref"] = raw_payload.repo_ref
    elif isinstance(raw_payload, dict) and "repo_ref" in raw_payload:
        params["repo_ref"] = raw_payload["repo_ref"]
    return params


def create_repository_node(mcp_gateway: MCPGateway, llm_provider: Optional[LLMProvider] = None):
    async def repository_node(state: DeveloperState) -> DeveloperState:
        # Budget circuit breakers
        if state.get("llm_calls_made", 0) >= 2:
            return {"error": f"[{ErrorTaxonomy.VALIDATION_INPUT.value}] Execution budget exceeded: maximum 2 LLM calls allowed."}
        if state.get("tool_calls_made", 0) >= 20 or mcp_gateway.tool_calls_count >= 20:
            return {"error": f"[{ErrorTaxonomy.VALIDATION_INPUT.value}] Execution budget exceeded: maximum 20 tool calls allowed."}

        agent = RepositoryAgent(mcp_gateway, llm_provider=llm_provider)
        try:
            params = _extract_agent_params(state)
            result = await agent.execute(params, state.get("trace_id", "N/A"))
            return {
                "agent_result": result,
                "tool_calls_made": mcp_gateway.tool_calls_count,
                "files_read_count": len(mcp_gateway.files_read),
            }
        except DeveloperBaseException as e:
            return {"error": f"[{e.code.value}] {scrub_secrets(e.message)}"}
        except Exception as e:
            return {"error": f"[{ErrorTaxonomy.INTERNAL.value}] {scrub_secrets(str(e))}"}
    return repository_node


def create_coding_node(mcp_gateway: MCPGateway, llm_provider: Optional[LLMProvider] = None):
    async def coding_node(state: DeveloperState) -> DeveloperState:
        # Budget circuit breakers
        if state.get("llm_calls_made", 0) >= 2:
            return {"error": f"[{ErrorTaxonomy.VALIDATION_INPUT.value}] Execution budget exceeded: maximum 2 LLM calls allowed."}
        if state.get("tool_calls_made", 0) >= 20 or mcp_gateway.tool_calls_count >= 20:
            return {"error": f"[{ErrorTaxonomy.VALIDATION_INPUT.value}] Execution budget exceeded: maximum 20 tool calls allowed."}

        mode = state.get("mode", "preview")
        agent = CodingAgent(mcp_gateway, mode=mode, llm_provider=llm_provider)
        try:
            params = _extract_agent_params(state)
            result = await agent.execute(params, state.get("trace_id", "N/A"))
            return {
                "agent_result": result,
                "tool_calls_made": mcp_gateway.tool_calls_count,
                "files_read_count": len(mcp_gateway.files_read),
            }
        except DeveloperBaseException as e:
            return {"error": f"[{e.code.value}] {scrub_secrets(e.message)}"}
        except Exception as e:
            return {"error": f"[{ErrorTaxonomy.INTERNAL.value}] {scrub_secrets(str(e))}"}
    return coding_node


def create_documentation_node(mcp_gateway: MCPGateway, llm_provider: Optional[LLMProvider] = None):
    async def documentation_node(state: DeveloperState) -> DeveloperState:
        # Budget circuit breakers
        if state.get("llm_calls_made", 0) >= 2:
            return {"error": f"[{ErrorTaxonomy.VALIDATION_INPUT.value}] Execution budget exceeded: maximum 2 LLM calls allowed."}
        if state.get("tool_calls_made", 0) >= 20 or mcp_gateway.tool_calls_count >= 20:
            return {"error": f"[{ErrorTaxonomy.VALIDATION_INPUT.value}] Execution budget exceeded: maximum 20 tool calls allowed."}

        mode = state.get("mode", "preview")
        agent = DocumentationAgent(mcp_gateway, mode=mode, llm_provider=llm_provider)
        try:
            params = _extract_agent_params(state)
            result = await agent.execute(params, state.get("trace_id", "N/A"))
            return {
                "agent_result": result,
                "tool_calls_made": mcp_gateway.tool_calls_count,
                "files_read_count": len(mcp_gateway.files_read),
            }
        except DeveloperBaseException as e:
            return {"error": f"[{e.code.value}] {scrub_secrets(e.message)}"}
        except Exception as e:
            return {"error": f"[{ErrorTaxonomy.INTERNAL.value}] {scrub_secrets(str(e))}"}
    return documentation_node


# 4. Normalization Node
def create_format_result_node(mcp_gateway: MCPGateway):
    def format_result_node(state: DeveloperState) -> DeveloperState:
        """Formats the agent result into DeveloperResponse or DeveloperTaskOutput."""
        raw_input = state.get("input_payload")
        is_dev_request = isinstance(raw_input, DeveloperRequest) or (
            isinstance(raw_input, dict) and "prompt" in raw_input and "task_type" in raw_input
        )
        task_type = state.get("task_type") or TaskType.REPO_ANALYSIS
        mode_val = state.get("mode") or "preview"
        mode_enum = DeveloperMode.APPLY if mode_val == "apply" else DeveloperMode.PREVIEW

        if state.get("error"):
            err_msg = state["error"]
            task_output = DeveloperTaskOutput(
                result={"error": err_msg},
                artifacts=[],
                status=TaskStatus.ERROR
            )
            dev_response = DeveloperResponse(
                status=TaskStatus.ERROR,
                task_type=task_type,
                mode=mode_enum,
                summary=f"Task execution failed: {err_msg}",
                files_analyzed=list(mcp_gateway.files_read),
                proposed_patches=[],
                documentation=None,
                warnings=[err_msg],
                tool_events=mcp_gateway.events,
                metadata={
                    "tool_calls_made": mcp_gateway.tool_calls_count,
                    "files_read_count": len(mcp_gateway.files_read),
                    "cumulative_read_bytes": mcp_gateway.cumulative_read_bytes,
                }
            )
            return {
                "output_payload": dev_response if is_dev_request else task_output,
                "developer_response": dev_response
            }

        agent_res = state.get("agent_result", {}) or {}
        artifacts = []
        proposed_patches: List[ProposedPatch] = []
        documentation = None

        if task_type == TaskType.CODE_GEN:
            artifacts = agent_res.get("files_changed", [])
            for patch_data in agent_res.get("proposed_patches", []):
                try:
                    proposed_patches.append(ProposedPatch(**patch_data))
                except Exception:
                    pass
        elif task_type == TaskType.DOC_GEN:
            if agent_res.get("artifact"):
                artifacts = [agent_res["artifact"]]
            documentation = agent_res.get("content")

        task_output = DeveloperTaskOutput(
            result=agent_res,
            artifacts=artifacts,
            status=TaskStatus.SUCCESS
        )

        dev_response = DeveloperResponse(
            status=TaskStatus.SUCCESS,
            task_type=task_type,
            mode=mode_enum,
            summary=str(agent_res.get("summary", "Developer task completed successfully.")),
            files_analyzed=list(mcp_gateway.files_read),
            proposed_patches=proposed_patches,
            documentation=documentation,
            warnings=list(agent_res.get("warnings", [])),
            tool_events=mcp_gateway.events,
            metadata={
                "tool_calls_made": mcp_gateway.tool_calls_count,
                "files_read_count": len(mcp_gateway.files_read),
                "cumulative_read_bytes": mcp_gateway.cumulative_read_bytes,
            }
        )

        return {
            "output_payload": dev_response if is_dev_request else task_output,
            "developer_response": dev_response
        }
    return format_result_node


# 5. Graph Compiler
def compile_developer_subgraph(mcp_gateway: MCPGateway, llm_provider: Optional[LLMProvider] = None):
    """
    Compiles and returns the isolated Developer Subgraph executable graph.
    """
    graph = StateGraph(DeveloperState)

    format_node = create_format_result_node(mcp_gateway)

    graph.add_node("validate", validate_task_node)
    graph.add_node("repository_agent", create_repository_node(mcp_gateway, llm_provider))
    graph.add_node("coding_agent", create_coding_node(mcp_gateway, llm_provider))
    graph.add_node("documentation_agent", create_documentation_node(mcp_gateway, llm_provider))
    graph.add_node("format_result", format_node)
    graph.add_node("format_error", format_node)

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
