import hashlib
import json
import re
from typing import Any, Dict, List, Optional

from app.developer.agents.base import BaseAgent
from app.developer.schemas import DocAgentResult, ToolRequest, ToolResponseStatus
from app.developer.mcp.gateway import MCPGateway
from app.developer.logging import StructuredLogger
from app.developer.prompts.escaping import escape_prompt_data
from app.developer.budget import LLMCallBudget, LLMCallBudgetExceededError
from app.research.llm.base import LLMProvider


class DocumentationAgent(BaseAgent):
    def __init__(
        self,
        mcp_gateway: MCPGateway,
        mode: str = "preview",
        llm_provider: Optional[LLMProvider] = None,
        call_budget: Optional[LLMCallBudget] = None,
    ):
        self.mcp = mcp_gateway
        self.mode = mode
        self.llm_provider = llm_provider
        self.call_budget = call_budget
        self.logger = StructuredLogger("documentation-agent")

    async def _call_tool(self, tool_name: str, arguments: dict, trace_id: str) -> Any:
        req = ToolRequest(tool_name=tool_name, arguments=arguments, request_id=trace_id)
        res = await self.mcp.dispatch(req)
        if res.status == ToolResponseStatus.ERROR:
            self.logger.warn(f"Tool {tool_name} failed: {res.error_code} - {res.result}", trace_id=trace_id)
            return None
        return res.result

    def _sanitize_text(self, text: str) -> str:
        """Neutralizes prompt injection keywords and removes control characters."""
        if not isinstance(text, str):
            return str(text)
        # Strip ASCII control characters except newline and tab
        clean = "".join(ch for ch in text if ch in ('\n', '\t') or (ord(ch) >= 32 and ord(ch) != 127))
        # Mask common prompt injection phrases
        injection_phrases = [
            "ignore previous instructions",
            "ignore all previous instructions",
            "disregard previous instructions",
            "system prompt",
            "[inst]",
            "[/inst]",
            "<|im_start|>",
            "<|im_end|>"
        ]
        for phrase in injection_phrases:
            if phrase in clean.lower():
                pattern = re.compile(re.escape(phrase), re.IGNORECASE)
                clean = pattern.sub(f"[FILTERED_INJECTION: {phrase}]", clean)
        return clean

    def _generate_markdown(self, doc_type: str, context: Dict[str, Any]) -> str:
        """
        Deterministically builds markdown based ONLY on verified repository context.
        Prevents hallucinating endpoints or deps by falling back to 'Unknown'.
        """
        lines = []
        clean_doc_type = self._sanitize_text(doc_type)

        if doc_type == "repository_summary" or doc_type == "README":
            lines.append(f"# {clean_doc_type.upper()}")
            lines.append("")
            
            langs = [self._sanitize_text(l) for l in context.get("languages", [])]
            lines.append(f"**Languages:** {', '.join(langs) if langs else 'Unknown'}")
            
            deps = [self._sanitize_text(d) for d in context.get("dependencies", [])]
            lines.append(f"**Dependencies:** {', '.join(deps) if deps else 'Unknown'}")
            
            eps = [self._sanitize_text(e) for e in context.get("entry_points", [])]
            lines.append(f"**Entry Points:** {', '.join(eps) if eps else 'Unknown'}")
            
        elif doc_type == "architecture":
            lines.append("# Architecture Details")
            arch = context.get("architecture", {})
            inferred = self._sanitize_text(str(arch.get("inferred", "Unknown Architecture Pattern")))
            lines.append(inferred)
            
        else:
            lines.append(f"# {clean_doc_type}")
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
            
        sources = repo_context.get("important_files", [])
        
        # Generate the safe, deterministic content
        content = self._generate_markdown(doc_type, repo_context)

        # If LLM provider is present and context is verified, synthesize rich markdown
        if self.llm_provider and repo_context:
            try:
                if self.call_budget is not None:
                    self.call_budget.consume()

                system_prompt = (
                    "You are Orchestra's Documentation Agent. Generate markdown documentation strictly grounded in the verified context.\n"
                    "Never invent dependencies or entry points. If information is not in the context, explicitly write 'Unknown'."
                )
                safe_doc_type = escape_prompt_data(self._sanitize_text(doc_type))
                repo_str = json.dumps(repo_context, default=str) if isinstance(repo_context, dict) else str(repo_context)
                safe_repo_context = escape_prompt_data(repo_str)
                user_prompt = (
                    f"<SYSTEM_INSTRUCTIONS>\n{system_prompt}\n</SYSTEM_INSTRUCTIONS>\n"
                    f"<DOCUMENT_TYPE>{safe_doc_type}</DOCUMENT_TYPE>\n"
                    f"<UNTRUSTED_REPOSITORY_DATA>\n{safe_repo_context}\n</UNTRUSTED_REPOSITORY_DATA>\n"
                )
                llm_content = await self.llm_provider.generate_text(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=0.0
                )
                if llm_content and llm_content.strip():
                    content = self._sanitize_text(llm_content.strip())
            except LLMCallBudgetExceededError as e:
                self.logger.warning(f"LLM call budget exhausted: {e}", trace_id=trace_id)
                warnings.append(f"LLM call budget exhausted: {e}")
            except Exception as e:
                self.logger.warning(f"LLM documentation generation failed, fell back to deterministic template: {e}", trace_id=trace_id)
        
        artifact_saved = None
        
        if self.mode == "apply" and output_path:
            old_doc = await self._call_tool("read_file", {"path": output_path}, trace_id)
            expected_hash = hashlib.sha256(old_doc.encode("utf-8")).hexdigest() if old_doc is not None else None
            res = await self._call_tool(
                "write_file",
                {"path": output_path, "content": content, "expected_hash": expected_hash},
                trace_id
            )
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
