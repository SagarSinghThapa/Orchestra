import json
from typing import Any, Dict

from app.developer.agents.base import BaseAgent
from app.developer.schemas import RepositoryAnalysisResult, ToolRequest, ToolResponseStatus
from app.developer.mcp.gateway import MCPGateway
from app.developer.logging import StructuredLogger


class RepositoryAgent(BaseAgent):
    def __init__(self, mcp_gateway: MCPGateway, max_files_to_read: int = 10, max_file_size_bytes: int = 1024 * 50):
        self.mcp = mcp_gateway
        self.max_files_to_read = max_files_to_read
        self.max_file_size_bytes = max_file_size_bytes
        self.logger = StructuredLogger("repository-agent")

    async def _call_tool(self, tool_name: str, arguments: dict, trace_id: str) -> Any:
        req = ToolRequest(tool_name=tool_name, arguments=arguments, request_id=trace_id)
        res = await self.mcp.dispatch(req)
        if res.status == ToolResponseStatus.ERROR:
            self.logger.warn(f"Tool {tool_name} failed: {res.error_code} - {res.result}", trace_id=trace_id)
            return None
        return res.result

    async def execute(self, params: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        """
        Executes a staged, deterministic repository analysis using MCP tools.
        """
        repo_ref = str(params.get("repo_ref", "")).strip()
        if "\0" in repo_ref:
            self.logger.warn(f"Null byte detected in repo_ref", trace_id=trace_id)
            repo_ref = ""

        self.logger.info(f"Starting analysis for repo: {repo_ref}", trace_id=trace_id)

        # Stage 1: Deterministic inspection
        # Get tree
        tree_str = await self._call_tool("repo_tree", {"path": repo_ref}, trace_id)
        if not tree_str:
            tree_str = ""

        # Identify important configuration files
        manifests = ["package.json", "requirements.txt", "pyproject.toml", "pytest.ini", "tsconfig.json", "main.py", "app.py"]
        
        file_contents = {}
        for m in manifests:
            if len(file_contents) >= self.max_files_to_read:
                break
            matches = await self._call_tool("search_files", {"pattern": m}, trace_id)
            if matches:
                for match in matches[:2]:  # Limit duplicates
                    if len(file_contents) >= self.max_files_to_read:
                        break
                    meta = await self._call_tool("file_metadata", {"path": match}, trace_id)
                    if meta and not meta.get("is_dir") and meta.get("size", 0) <= self.max_file_size_bytes:
                        content = await self._call_tool("read_file", {"path": match}, trace_id)
                        if content:
                            file_contents[match] = content

                            
        # Stage 2: Interpretation
        # (This is stubbed logically for Phase 3, avoiding massive LLM context)
        analysis = self._interpret_findings(tree_str, file_contents)
        
        self.logger.info("Repository analysis complete.", trace_id=trace_id)
        return analysis.model_dump()

    def _interpret_findings(self, tree: str, file_contents: Dict[str, str]) -> RepositoryAnalysisResult:
        """
        Heuristic interpretation. In production, this can invoke an LLM payload,
        but strictly bounded by the `file_contents` mapping.
        """
        languages = []
        if "pyproject.toml" in str(file_contents) or "requirements.txt" in str(file_contents) or ".py" in tree:
            languages.append("Python")
        if "package.json" in str(file_contents) or ".js" in tree or ".ts" in tree:
            languages.append("JavaScript/TypeScript")

        frameworks = []
        if any("fastapi" in c.lower() for c in file_contents.values()):
            frameworks.append("FastAPI")
        if any("react" in c.lower() or "next" in c.lower() for c in file_contents.values()):
            frameworks.append("React/Next.js")

        return RepositoryAnalysisResult(
            repository={"tree_size": len(tree.split("\n"))},
            languages=languages,
            frameworks=frameworks,
            architecture={"inferred": "Monolith or Microservices"},
            important_files=list(file_contents.keys()),
            dependencies=[],
            entry_points=["main.py"] if "main.py" in tree else [],
            modules=[],
            tests={"has_tests": "test" in tree.lower()},
            risks=["Stub heuristic evaluation - replace with LLM in later phase."],
            recommendations=["Proceed to Coding Agent."]
        )
