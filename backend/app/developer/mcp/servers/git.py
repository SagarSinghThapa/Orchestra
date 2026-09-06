import asyncio
import shutil
from pathlib import Path
from typing import Any, Dict

from app.developer.mcp.tools.base import BaseTool
from app.developer.schemas import ToolRegistration
from app.developer.errors import InternalError, ValidationError, TimeoutError

GIT_COMMAND_TIMEOUT_SECONDS = 10.0
MAX_LOG_LIMIT = 100


class GitBaseTool(BaseTool):
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root

    async def _run_git_command(self, *args: str) -> str:
        # 1. Verify workspace exists
        if not Path(self.workspace_root).is_dir():
            raise InternalError(f"Workspace directory does not exist: {self.workspace_root}")

        # 2. Verify git executable exists
        if not shutil.which("git"):
            raise InternalError("Git executable not found in system PATH.")

        try:
            process = await asyncio.create_subprocess_exec(
                "git", *args,
                cwd=self.workspace_root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        except Exception as e:
            raise InternalError(f"Failed to spawn git process: {e}")

        # 3. Timeout handling with process cleanup
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=GIT_COMMAND_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            try:
                process.kill()
                await process.wait()
            except Exception:
                pass
            raise TimeoutError(f"Git command 'git {' '.join(args)}' timed out after {GIT_COMMAND_TIMEOUT_SECONDS}s.")

        if process.returncode != 0:
            err_msg = stderr.decode().strip()
            raise InternalError(f"Git command failed: {err_msg}")
            
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
            description="Gets the git diff with argument injection protection.",
            input_schema={
                "type": "object",
                "properties": {
                    "file": {"type": "string", "description": "Optional file path to diff"}
                }
            }
        )

    async def execute(self, arguments: Dict[str, Any], trace_id: str) -> Any:
        args = ["diff"]
        if "file" in arguments and arguments["file"]:
            file_arg = str(arguments["file"]).strip()
            # Guard against flag injection
            if file_arg.startswith("-"):
                raise ValidationError(f"Invalid file path for git diff: '{file_arg}' cannot start with a dash.")
            # Use positional barrier -- to prevent any interpretation as flags
            args.extend(["--", file_arg])
        return await self._run_git_command(*args)


class GitLogTool(GitBaseTool):
    @property
    def registration(self) -> ToolRegistration:
        return ToolRegistration(
            name="git_log",
            description="Gets recent git commit log with bounded limit.",
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of commits (1-100)"}
                }
            }
        )

    async def execute(self, arguments: Dict[str, Any], trace_id: str) -> Any:
        limit_val = arguments.get("limit", 10)
        try:
            limit = int(limit_val)
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid limit '{limit_val}': must be an integer.")

        if limit < 1 or limit > MAX_LOG_LIMIT:
            raise ValidationError(f"Limit must be between 1 and {MAX_LOG_LIMIT}, got {limit}.")

        return await self._run_git_command("log", "-n", str(limit), "--oneline")

