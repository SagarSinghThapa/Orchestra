import asyncio
import logging
import uuid
from typing import Optional
from sqlalchemy.orm import Session

from app.developer.workspace import WorkspaceResolver
from app.developer.mcp.gateway import MCPGateway
from app.developer.mcp.servers.filesystem import (
    ReadFileTool,
    WriteFileTool,
    ListFilesTool,
    SearchFilesTool,
)
from app.developer.mcp.servers.repository import (
    RepoTreeTool,
    FileMetadataTool,
    SearchCodeTool,
)
from app.developer.mcp.servers.git import (
    GitStatusTool,
    GitDiffTool,
    GitLogTool,
)
from app.developer.mcp.utils.sandbox import resolve_safe_path
from app.developer.graph.graph import compile_developer_subgraph
from app.developer.schemas import DeveloperRequest, DeveloperResponse, DeveloperMode, TaskStatus
from app.developer.errors import ValidationError, TimeoutError
from app.research.llm.base import LLMProvider
from app.research.llm.provider import get_llm_provider

logger = logging.getLogger("developer-service")


class DeveloperService:
    """
    Orchestration facade for Developer Intelligence tasks.
    Manages workspace resolution, tool mounting, request-local LangGraph compilation,
    and enforces a global 45.0s execution timeout ceiling.
    """

    def __init__(
        self,
        db: Optional[Session] = None,
        workspace_resolver: Optional[WorkspaceResolver] = None,
        llm_provider: Optional[LLMProvider] = None,
        timeout_seconds: float = 45.0,
    ):
        self.db = db
        self.workspace_resolver = workspace_resolver or WorkspaceResolver()
        self.timeout_seconds = timeout_seconds
        if llm_provider is not None:
            self.llm_provider = llm_provider
        else:
            try:
                self.llm_provider = get_llm_provider()
            except Exception:
                self.llm_provider = None

    async def execute_task(
        self,
        project_id: int,
        request: DeveloperRequest,
        trace_id: Optional[str] = None,
    ) -> DeveloperResponse:
        """
        Executes a project-scoped developer task.
        Validates target file boundaries, resolves workspace root, initialises bounded MCP tools,
        and runs the Developer LangGraph state machine within the global deadline.
        """
        tid = trace_id or f"trace-dev-{uuid.uuid4().hex[:8]}"
        logger.info(f"Starting developer task for project {project_id} in {request.mode.value} mode", extra={"trace_id": tid})

        # 1. Resolve and ensure project workspace
        workspace_root = self.workspace_resolver.ensure_workspace(project_id)
        ws_str = str(workspace_root)

        # 2. Validate target_files up front if provided
        if request.target_files:
            for target_path in request.target_files:
                resolve_safe_path(ws_str, target_path)

        # 3. Mount project-scoped MCP tools
        gateway = MCPGateway(execution_timeout_seconds=30.0)
        gateway.register_tool(ReadFileTool(ws_str))
        gateway.register_tool(WriteFileTool(ws_str))
        gateway.register_tool(ListFilesTool(ws_str))
        gateway.register_tool(SearchFilesTool(ws_str))
        gateway.register_tool(RepoTreeTool(ws_str))
        gateway.register_tool(FileMetadataTool(ws_str))
        gateway.register_tool(SearchCodeTool(ws_str))
        gateway.register_tool(GitStatusTool(ws_str))
        gateway.register_tool(GitDiffTool(ws_str))
        gateway.register_tool(GitLogTool(ws_str))

        # 4. Compile isolated Developer LangGraph
        graph = compile_developer_subgraph(mcp_gateway=gateway, llm_provider=self.llm_provider)

        # 5. Execute state machine under global deadline
        try:
            async with asyncio.timeout(self.timeout_seconds):
                state_result = await graph.ainvoke({
                    "input_payload": request,
                    "trace_id": tid,
                    "workspace_root": ws_str,
                    "mode": request.mode.value if hasattr(request.mode, "value") else str(request.mode),
                    "prompt": request.prompt,
                    "target_files": request.target_files,
                    "expected_file_hashes": request.expected_file_hashes,
                    "context_hints": request.context_hints,
                    "llm_calls_made": 0,
                    "tool_calls_made": 0,
                    "files_read_count": 0,
                })
        except asyncio.TimeoutError as exc:
            logger.error(f"Developer task timed out after {self.timeout_seconds}s for project {project_id}", extra={"trace_id": tid})
            raise TimeoutError(f"Developer task timed out after {self.timeout_seconds}s") from exc

        # 6. Extract DeveloperResponse
        dev_response = state_result.get("developer_response")
        if isinstance(dev_response, DeveloperResponse):
            return dev_response

        output = state_result.get("output_payload")
        if isinstance(output, DeveloperResponse):
            return output

        # Fallback response normalization
        return DeveloperResponse(
            status=TaskStatus.SUCCESS,
            task_type=request.task_type,
            mode=request.mode,
            summary="Developer task completed successfully.",
            files_analyzed=list(gateway.files_read),
            proposed_patches=[],
            documentation=None,
            warnings=[],
            tool_events=gateway.events,
            metadata={
                "tool_calls_made": gateway.tool_calls_count,
                "files_read_count": len(gateway.files_read),
                "cumulative_read_bytes": gateway.cumulative_read_bytes,
            }
        )
