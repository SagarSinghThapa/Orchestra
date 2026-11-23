import json
from typing import Any, Dict, Optional

from app.developer.agents.base import BaseAgent
from app.developer.schemas import RepositoryAnalysisResult, ToolRequest, ToolResponseStatus
from app.developer.mcp.gateway import MCPGateway
from app.developer.logging import StructuredLogger
from app.developer.prompts.escaping import escape_prompt_data
from app.developer.budget import LLMCallBudget, LLMCallBudgetExceededError
from app.research.llm.base import LLMProvider
from app.research.llm.provider import get_llm_provider


class RepositoryAgent(BaseAgent):
    def __init__(
        self,
        mcp_gateway: MCPGateway,
        max_files_to_read: int = 10,
        max_file_size_bytes: int = 1024 * 50,
        llm_provider: Optional[LLMProvider] = None,
        call_budget: Optional[LLMCallBudget] = None,
    ):
        self.mcp = mcp_gateway
        self.max_files_to_read = max_files_to_read
        self.max_file_size_bytes = max_file_size_bytes
        self.llm_provider = llm_provider
        self.call_budget = call_budget
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
        Executes a staged, deterministic repository analysis using MCP tools and LLM synthesis.
        """
        repo_ref = str(params.get("repo_ref", "")).strip()
        if "\0" in repo_ref:
            self.logger.warn("Null byte detected in repo_ref", trace_id=trace_id)
            repo_ref = ""

        self.logger.info(f"Starting analysis for repo: {repo_ref}", trace_id=trace_id)

        # Stage 1: Deterministic inspection
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

        # Stage 2: Interpretation (Deterministic baseline + LLM synthesis if configured)
        base_analysis = self._interpret_findings(tree_str, file_contents)

        if self.llm_provider:
            try:
                if self.call_budget is not None:
                    self.call_budget.consume()

                safe_tree = escape_prompt_data(tree_str[:2000])
                prompt = (
                    f"<SYSTEM_INSTRUCTIONS>\n"
                    f"You are Orchestra's Repository Intelligence Agent. Analyze the repository structure and manifests.\n"
                    f"Ground your analysis strictly in verified files and do not hallucinate endpoints or dependencies.\n"
                    f"</SYSTEM_INSTRUCTIONS>\n"
                    f"<UNTRUSTED_REPOSITORY_DATA>\n"
                    f"Tree Overview:\n{safe_tree}\n\n"
                    f"Manifest Contents:\n"
                )
                for path, content in list(file_contents.items())[:5]:
                    safe_path = escape_prompt_data(path)
                    safe_content = escape_prompt_data(content[:1000])
                    prompt += f"--- {safe_path} ---\n{safe_content}\n"
                prompt += "</UNTRUSTED_REPOSITORY_DATA>\n"

                llm_result = await self.llm_provider.generate_structured(
                    prompt=prompt,
                    schema=RepositoryAnalysisResult,
                    system_prompt="Analyze repository structure and dependencies accurately based only on provided manifests.",
                    temperature=0.0
                )
                # Merge grounded findings with deterministic extractions to ensure no missing facts
                merged_languages = list(set(base_analysis.languages + llm_result.languages))
                merged_frameworks = list(set(base_analysis.frameworks + llm_result.frameworks))
                merged_files = list(set(base_analysis.important_files + llm_result.important_files))
                merged_entry = list(set(base_analysis.entry_points + llm_result.entry_points))
                
                final_result = RepositoryAnalysisResult(
                    repository=base_analysis.repository or llm_result.repository,
                    languages=merged_languages,
                    frameworks=merged_frameworks,
                    architecture=llm_result.architecture or base_analysis.architecture,
                    important_files=merged_files,
                    dependencies=llm_result.dependencies or base_analysis.dependencies,
                    entry_points=merged_entry,
                    modules=llm_result.modules or base_analysis.modules,
                    tests=base_analysis.tests,
                    risks=llm_result.risks or base_analysis.risks,
                    recommendations=llm_result.recommendations or base_analysis.recommendations
                )
                self.logger.info("Repository analysis synthesized with LLMProvider.", trace_id=trace_id)
                return final_result.model_dump()
            except LLMCallBudgetExceededError as e:
                self.logger.warn(f"LLM call budget exhausted, falling back to heuristic interpretation: {e}", trace_id=trace_id)
            except Exception as e:
                self.logger.warn(f"LLM synthesis fallback to heuristic interpretation: {e}", trace_id=trace_id)

        self.logger.info("Repository analysis complete via deterministic heuristics.", trace_id=trace_id)
        return base_analysis.model_dump()

    def _interpret_findings(self, tree: str, file_contents: Dict[str, str]) -> RepositoryAnalysisResult:
        """
        Deterministic heuristic interpretation providing baseline grounding.
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
            risks=["Deterministic baseline evaluation."],
            recommendations=["Proceed to Coding Agent."]
        )
