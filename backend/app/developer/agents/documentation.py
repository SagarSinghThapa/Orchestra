from typing import Any, Dict, List

from app.developer.agents.base import BaseAgent
from app.developer.schemas import DocAgentResult, ToolRequest, ToolResponseStatus
from app.developer.mcp.gateway import MCPGateway
from app.developer.logging import StructuredLogger


class DocumentationAgent(BaseAgent):
    def __init__(self, mcp_gateway: MCPGateway, mode: str = "preview"):
        self.mcp = mcp_gateway
        self.mode = mode
        self.logger = StructuredLogger("documentation-agent")

    async def _call_tool(self, tool_name: str, arguments: dict, trace_id: str) -> Any:
        req = ToolRequest(tool_name=tool_name, arguments=arguments, request_id=trace_id)
        res = await self.mcp.dispatch(req)
        if res.status == ToolResponseStatus.ERROR:
            self.logger.warn(f"Tool {tool_name} failed: {res.error_code} - {res.result}", trace_id=trace_id)
            return None
        return res.result

    def _generate_markdown(self, doc_type: str, context: Dict[str, Any]) -> str:
        """
        Deterministically builds markdown based ONLY on verified repository context.
        Prevents hallucinating endpoints or deps by falling back to 'Unknown'.
        """
        lines = []
        if doc_type == "repository_summary" or doc_type == "README":
            lines.append(f"# {doc_type.upper()}")
            lines.append("")
            
            # Use deterministic context
            langs = context.get("languages", [])
            lines.append(f"**Languages:** {', '.join(langs) if langs else 'Unknown'}")
            
            deps = context.get("dependencies", [])
            lines.append(f"**Dependencies:** {', '.join(deps) if deps else 'Unknown'}")
            
            eps = context.get("entry_points", [])
            lines.append(f"**Entry Points:** {', '.join(eps) if eps else 'Unknown'}")
            
        elif doc_type == "architecture":
            lines.append("# Architecture Details")
            arch = context.get("architecture", {})
            lines.append(str(arch.get("inferred", "Unknown Architecture Pattern")))
            
        else:
            lines.append(f"# {doc_type}")
            lines.append("Content generated from repository context.")
            
        return "\n".join(lines)

    async def execute(self, params: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        """
        Executes a documentation task using pre-validated repository context.
        """
        doc_type = params.get("doc_type", "README")
        repo_context = params.get("repository_context", {})
        output_path = params.get("output_path", None)
        
        self.logger.info(f"Starting documentation agent for {doc_type} in {self.mode} mode", trace_id=trace_id)
        
        warnings = []
        if not repo_context:
            warnings.append("No verified repository context provided. Generating limited document.")
            
        # Ensure we only use verified sources (simulated extraction for Phase 3.3)
        sources = repo_context.get("important_files", [])
        
        # Generate the safe, deterministic content
        content = self._generate_markdown(doc_type, repo_context)
        
        artifact_saved = None
        
        if self.mode == "apply" and output_path:
            res = await self._call_tool("write_file", {"path": output_path, "content": content}, trace_id)
            if res and res.get("success"):
                artifact_saved = output_path
                self.logger.info(f"Successfully wrote documentation to {output_path}", trace_id=trace_id)
            else:
                warnings.append(f"Failed to write artifact to {output_path}")
        elif self.mode == "preview":
            self.logger.info("Preview mode: Documentation generated but not saved.", trace_id=trace_id)
            
        result = DocAgentResult(
            document_type=doc_type,
            content=content,
            sources=sources,
            artifact=artifact_saved,
            warnings=warnings
        )
        
        return result.model_dump()
