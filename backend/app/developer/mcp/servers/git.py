import asyncio
from typing import Any, Dict

from app.developer.mcp.tools.base import BaseTool
from app.developer.schemas import ToolRegistration
from app.developer.errors import InternalError


class GitBaseTool(BaseTool):
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root

    async def _run_git_command(self, *args: str) -> str:
        process = await asyncio.create_subprocess_exec(
            "git", *args,
            cwd=self.workspace_root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise InternalError(f"Git command failed: {stderr.decode().strip()}")
        return stdout.decode().strip()


class GitStatusTool(GitBaseTool):
    @property
    def registration(self) -> ToolRegistration:
        return ToolRegistration(
            name="git_status",
            description="Gets the current git status (short format).",
            input_schema={"type": "object", "properties": {}}
        )

    async def execute(self, arguments: Dict[str, Any], trace_id: str) -> Any:
        return await self._run_git_command("status", "-s")


class GitDiffTool(GitBaseTool):
    @property
    def registration(self) -> ToolRegistration:
        return ToolRegistration(
            name="git_diff",
            description="Gets the git diff.",
            input_schema={
                "type": "object",
                "properties": {
                    "file": {"type": "string", "description": "Optional file path to diff"}
                }
            }
        )

    async def execute(self, arguments: Dict[str, Any], trace_id: str) -> Any:
        args = ["diff"]
        if "file" in arguments:
            args.append(arguments["file"])
        return await self._run_git_command(*args)


class GitLogTool(GitBaseTool):
    @property
    def registration(self) -> ToolRegistration:
        return ToolRegistration(
            name="git_log",
            description="Gets the recent git commit log.",
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of commits"}
                }
            }
        )

    async def execute(self, arguments: Dict[str, Any], trace_id: str) -> Any:
        limit = str(arguments.get("limit", 10))
        return await self._run_git_command("log", f"-n {limit}", "--oneline")
