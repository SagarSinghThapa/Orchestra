import ast
import difflib
from typing import Any, Dict, List

from app.developer.agents.base import BaseAgent
from app.developer.schemas import CodingAgentResult, ToolRequest, ToolResponseStatus
from app.developer.mcp.gateway import MCPGateway
from app.developer.logging import StructuredLogger


class CodingAgent(BaseAgent):
    def __init__(self, mcp_gateway: MCPGateway, mode: str = "preview", max_files_changed: int = 5):
        self.mcp = mcp_gateway
        self.mode = mode
        self.max_files_changed = max_files_changed
        self.allowed_extensions = {".py", ".js", ".ts", ".html", ".css", ".md", ".json"}
        self.logger = StructuredLogger("coding-agent")

    async def _call_tool(self, tool_name: str, arguments: dict, trace_id: str) -> Any:
        req = ToolRequest(tool_name=tool_name, arguments=arguments, request_id=trace_id)
        res = await self.mcp.dispatch(req)
        if res.status == ToolResponseStatus.ERROR:
            self.logger.warn(f"Tool {tool_name} failed: {res.error_code} - {res.result}", trace_id=trace_id)
            return None
        return res.result

    def _validate_syntax(self, path: str, content: str) -> str:
        if not path.endswith(".py"):
            return "Skipped (non-python)"
        try:
            ast.parse(content)
            return "Valid"
        except SyntaxError as e:
            return f"SyntaxError: {e}"
        except Exception as e:
            return f"Error: {e}"

    def _generate_diff(self, path: str, old_content: str, new_content: str) -> str:
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines, new_lines, fromfile=f"a/{path}", tofile=f"b/{path}"
        )
        return "".join(diff)

    async def execute(self, params: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        """
        Executes a PLAN-FIRST coding task using MCP tools.
        """
        repo_ref = params.get("repo_ref", "")
        # `proposed_changes` format: {"path": "new_content"}
        # For Phase 4, we assume the params contain the mocked "proposed_changes" 
        # since we aren't hooking up the LLM generator yet.
        proposed_changes: Dict[str, str] = params.get("proposed_changes", {})
        
        self.logger.info(f"Starting coding agent for repo: {repo_ref} in {self.mode} mode", trace_id=trace_id)
        
        warnings = []
        files_changed = []
        diffs = {}
        validation = {}
        
        # Security checks
        if len(proposed_changes) > self.max_files_changed:
            msg = f"Proposed changes exceed max allowed ({len(proposed_changes)} > {self.max_files_changed})."
            warnings.append(msg)
            return CodingAgentResult(
                summary="Failed due to max files limit.", plan=[], files_changed=[], diffs={}, validation={}, warnings=warnings
            ).model_dump()
            
        for path, new_content in proposed_changes.items():
            ext = "." + path.split(".")[-1] if "." in path else ""
            if ext not in self.allowed_extensions:
                warnings.append(f"Extension not allowed for {path}")
                continue
                
            files_changed.append(path)
            
            # Read old content
            old_content = await self._call_tool("read_file", {"path": path}, trace_id)
            if old_content is None:
                old_content = ""
                
            # Diff
            diff = self._generate_diff(path, old_content, new_content)
            diffs[path] = diff
            
            # Validate
            val_status = self._validate_syntax(path, new_content)
            validation[path] = val_status
            if val_status.startswith("SyntaxError") or val_status.startswith("Error"):
                warnings.append(f"Validation failed for {path}: {val_status}")

        summary = f"Generated {len(files_changed)} files."
        
        # Apply mode
        if self.mode == "apply":
            # Check if any critical warnings block applying
            if any("Validation failed" in w for w in warnings):
                summary = "Apply aborted due to validation failures."
            else:
                for path in files_changed:
                    res = await self._call_tool("write_file", {"path": path, "content": proposed_changes[path]}, trace_id)
                    if not res:
                        warnings.append(f"Failed to write {path}")
                if "Failed to write" not in "".join(warnings):
                    summary = f"Successfully applied changes to {len(files_changed)} files."
        else:
            summary += " (Preview mode only)."

        result = CodingAgentResult(
            summary=summary,
            plan=["Identify files", "Generate diffs", "Validate syntax", "Apply changes"],
            files_changed=files_changed,
            diffs=diffs,
            validation=validation,
            warnings=warnings
        )
        
        return result.model_dump()
