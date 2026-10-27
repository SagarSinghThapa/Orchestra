import ast
import difflib
import hashlib
from typing import Any, Dict, List, Optional

from app.developer.agents.base import BaseAgent
from app.developer.schemas import CodingAgentResult, ToolRequest, ToolResponseStatus
from app.developer.mcp.gateway import MCPGateway
from app.developer.logging import StructuredLogger
from app.research.llm.base import LLMProvider
from app.research.llm.provider import get_llm_provider


class CodingAgent(BaseAgent):
    def __init__(
        self,
        mcp_gateway: MCPGateway,
        mode: str = "preview",
        max_files_changed: int = 5,
        llm_provider: Optional[LLMProvider] = None,
    ):
        self.mcp = mcp_gateway
        self.mode = mode
        self.max_files_changed = max_files_changed
        self.allowed_extensions = {".py", ".js", ".ts", ".html", ".css", ".md", ".json"}
        if llm_provider is not None:
            self.llm_provider = llm_provider
        else:
            try:
                self.llm_provider = get_llm_provider()
            except Exception:
                self.llm_provider = None
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
        Executes a PLAN-FIRST coding task using MCP tools, AST validation,
        optimistic concurrency hash checking, and LLM code synthesis.
        """
        repo_ref = str(params.get("repo_ref", "")).strip()
        mode = params.get("mode", self.mode)
        prompt = str(params.get("prompt", "")).strip()
        target_files: List[str] = params.get("target_files", []) or []
        proposed_changes: Dict[str, str] = dict(params.get("proposed_changes", {}) or {})
        expected_file_hashes: Dict[str, str] = params.get("expected_file_hashes", {}) or {}

        self.logger.info(f"Starting coding agent for repo: {repo_ref} in {mode} mode", trace_id=trace_id)

        warnings: List[str] = []
        files_changed: List[str] = []
        diffs: Dict[str, str] = {}
        validation: Dict[str, str] = {}

        if not isinstance(proposed_changes, dict):
            return CodingAgentResult(
                summary="Failed due to invalid proposed_changes format (must be dict).",
                plan=[], files_changed=[], diffs={}, validation={}, warnings=["proposed_changes must be a dictionary"]
            ).model_dump()

        if len(proposed_changes) > self.max_files_changed or len(target_files) > self.max_files_changed:
            count = max(len(proposed_changes), len(target_files))
            msg = f"Proposed changes exceed max allowed ({count} > {self.max_files_changed})."
            warnings.append(msg)
            return CodingAgentResult(
                summary="Failed due to max files limit.", plan=[], files_changed=[], diffs={}, validation={}, warnings=warnings
            ).model_dump()

        # Capture pre-synthesis baseline hashes and synthesize if needed
        baseline_hashes: Dict[str, Optional[str]] = {}
        candidate_paths = list(proposed_changes.keys()) if proposed_changes else list(target_files)

        for path in candidate_paths:
            old_content = await self._call_tool("read_file", {"path": path}, trace_id)
            if old_content is not None:
                baseline_hashes[path] = hashlib.sha256(old_content.encode("utf-8")).hexdigest()
            else:
                baseline_hashes[path] = None

            # Synthesize if proposed_changes not pre-supplied
            if not proposed_changes and path in target_files and self.llm_provider and prompt:
                synthesis_prompt = (
                    f"<SYSTEM_INSTRUCTIONS>\n"
                    f"You are Orchestra's Coding Intelligence Agent. Generate updated source code for the requested file.\n"
                    f"Respond ONLY with the complete updated code. Do not wrap in markdown or include conversational explanations.\n"
                    f"</SYSTEM_INSTRUCTIONS>\n"
                    f"<TASK_PROMPT>\n{prompt}\n</TASK_PROMPT>\n"
                    f"<TARGET_PATH>{path}</TARGET_PATH>\n"
                    f"<EXISTING_CONTENT>\n{old_content or ''}\n</EXISTING_CONTENT>\n"
                )
                try:
                    synth_code = await self.llm_provider.generate_text(
                        prompt=synthesis_prompt,
                        system_prompt="Generate clean source code for the requested modifications.",
                        temperature=0.0
                    )
                    synth_clean = synth_code.strip()
                    if synth_clean.startswith("```"):
                        lines = synth_clean.splitlines()
                        if len(lines) >= 2 and lines[-1].strip() == "```":
                            synth_clean = "\n".join(lines[1:-1])
                    proposed_changes[path] = synth_clean
                except Exception as e:
                    self.logger.warn(f"LLM code synthesis failed for {path}: {e}", trace_id=trace_id)
                    warnings.append(f"LLM code synthesis failed for {path}: {e}")

        for path, new_content in proposed_changes.items():
            if not isinstance(path, str) or not isinstance(new_content, str):
                warnings.append("Invalid entry: path and content must be strings.")
                continue

            # Per file write limit (1MB)
            if len(new_content.encode("utf-8")) > 1024 * 1024:
                warnings.append(f"Proposed content for {path} exceeds 1MB limit.")
                continue

            ext = "." + path.split(".")[-1] if "." in path else ""
            if ext not in self.allowed_extensions:
                warnings.append(f"Extension not allowed for {path}")
                continue

            files_changed.append(path)

            old_content = await self._call_tool("read_file", {"path": path}, trace_id)
            if old_content is None:
                old_content = ""

            diff = self._generate_diff(path, old_content, new_content)
            diffs[path] = diff

            val_status = self._validate_syntax(path, new_content)
            validation[path] = val_status
            if val_status.startswith("SyntaxError") or val_status.startswith("Error"):
                warnings.append(f"Validation failed for {path}: {val_status}")

        summary = f"Generated {len(files_changed)} files."

        if mode == "apply":
            if any("Validation failed" in w for w in warnings):
                summary = "Apply aborted due to validation failures."
            else:
                concurrency_failed = False
                for path in files_changed:
                    # Check expected_file_hashes if supplied
                    if path in expected_file_hashes:
                        if expected_file_hashes[path] != baseline_hashes.get(path):
                            warnings.append(f"Concurrent modification detected for {path}")
                            concurrency_failed = True
                            continue
                    # Re-verify disk hash right before writing
                    disk_content = await self._call_tool("read_file", {"path": path}, trace_id)
                    disk_hash = hashlib.sha256(disk_content.encode("utf-8")).hexdigest() if disk_content is not None else None
                    if disk_hash != baseline_hashes.get(path):
                        warnings.append(f"Concurrent modification detected for {path}")
                        concurrency_failed = True

                if concurrency_failed:
                    summary = "Apply aborted due to concurrent modification."
                else:
                    for path in files_changed:
                        expected_hash = baseline_hashes.get(path)
                        res = await self._call_tool(
                            "write_file",
                            {"path": path, "content": proposed_changes[path], "expected_hash": expected_hash},
                            trace_id
                        )
                        if not res:
                            warnings.append(f"Failed to write {path}")
                    if not any("Failed to write" in w for w in warnings):
                        summary = f"Successfully applied changes to {len(files_changed)} files."
        else:
            summary += " (Preview mode only)."

        proposed_patches = []
        for path in files_changed:
            new_c = proposed_changes.get(path, "")
            new_h = hashlib.sha256(new_c.encode("utf-8")).hexdigest() if new_c else None
            is_applied = (
                mode == "apply"
                and "Successfully applied" in summary
                and not any(f"Failed to write {path}" in w for w in warnings)
            )
            proposed_patches.append({
                "path": path,
                "diff": diffs.get(path, ""),
                "validation_status": validation.get(path, ""),
                "original_hash": baseline_hashes.get(path),
                "new_hash": new_h,
                "applied": is_applied
            })

        result = CodingAgentResult(
            summary=summary,
            plan=["Identify files", "Capture baseline hashes", "Generate diffs", "Validate syntax", "Apply changes"],
            files_changed=files_changed,
            diffs=diffs,
            validation=validation,
            warnings=warnings,
            proposed_patches=proposed_patches
        )
        return result.model_dump()
