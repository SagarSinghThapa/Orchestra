import asyncio
import os
import shutil
from pathlib import Path
from typing import Any, Dict

from app.developer.mcp.tools.base import BaseTool
from app.developer.schemas import ToolRegistration
from app.developer.errors import InternalError, ValidationError, TimeoutError

GIT_COMMAND_TIMEOUT_SECONDS = 10.0
MAX_LOG_LIMIT = 100
MAX_GIT_OUTPUT_BYTES = 1024 * 1024  # 1 MB streaming limit


class GitBaseTool(BaseTool):
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root

    def _get_sanitized_environment(self) -> Dict[str, str]:
        """
        Constructs a minimal allowlist-based environment for child git processes.
        Strips host API keys, JWT secrets, and database credentials.
        Isolates global/system configuration and forces non-interactive pager.
        """
        SAFE_KEYS = {"PATH", "SYSTEMROOT", "SYSTEMDRIVE", "TEMP", "TMP", "USERPROFILE", "HOME"}
        env = {k: v for k, v in os.environ.items() if k.upper() in SAFE_KEYS}
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_CONFIG_GLOBAL"] = os.devnull
        env["GIT_PAGER"] = "cat"
        try:
            # Prevent git from walking up parent directories
            ceiling = str(Path(self.workspace_root).resolve().parent)
            env["GIT_CEILING_DIRECTORIES"] = ceiling
        except Exception:
            pass
        return env

    async def _read_bounded_stream(self, stream: asyncio.StreamReader, max_bytes: int) -> bytes:
        """Reads stream in chunks, raising ValidationError if cumulative bytes exceed max_bytes."""
        chunks = []
        total = 0
        while True:
            chunk = await stream.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValidationError(f"Git command output exceeded maximum allowable limit ({max_bytes} bytes).")
            chunks.append(chunk)
        return b"".join(chunks)

    async def _run_git_command(self, *args: str) -> str:
        # 1. Verify workspace exists
        workspace_path = Path(self.workspace_root).resolve()
        if not workspace_path.is_dir():
            raise InternalError(f"Workspace directory does not exist: {self.workspace_root}")

        # 2. Git upward discovery defense: require .git in workspace root
        git_dir = workspace_path / ".git"
        if not git_dir.is_dir():
            raise ValidationError(f"Workspace is not a Git repository: {self.workspace_root}")

        # 3. Verify git executable exists
        if not shutil.which("git"):
            raise InternalError("Git executable not found in system PATH.")

        try:
            process = await asyncio.create_subprocess_exec(
                "git", "--no-pager", *args,
                cwd=str(workspace_path),
                env=self._get_sanitized_environment(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        except Exception as e:
            raise InternalError(f"Failed to spawn git process: {e}")

        # 4. Timeout handling with streaming read bounds
        try:
            stdout_task = asyncio.create_task(self._read_bounded_stream(process.stdout, MAX_GIT_OUTPUT_BYTES))
            stderr_task = asyncio.create_task(self._read_bounded_stream(process.stderr, MAX_GIT_OUTPUT_BYTES))

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                asyncio.gather(stdout_task, stderr_task),
                timeout=GIT_COMMAND_TIMEOUT_SECONDS
            )
            await process.wait()

        except asyncio.TimeoutError:
            try:
                process.kill()
                await process.wait()
            except Exception:
                pass
            raise TimeoutError(f"Git command 'git {' '.join(args)}' timed out after {GIT_COMMAND_TIMEOUT_SECONDS}s.")
        except ValidationError:
            try:
                process.kill()
                await process.wait()
            except Exception:
                pass
            raise

        if process.returncode != 0:
            err_msg = stderr_bytes.decode(errors="replace").strip()
            raise InternalError(f"Git command failed: {err_msg}")
            
        return stdout_bytes.decode(errors="replace").strip()


class GitStatusTool(GitBaseTool):
    @property
    def registration(self) -> ToolRegistration:
        return ToolRegistration(
            name="git_status",
            description="Gets the current git status (short format).",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False}
        )

    async def execute(self, arguments: Dict[str, Any], trace_id: str) -> Any:
        return await self._run_git_command("status", "-s")


class GitDiffTool(GitBaseTool):
    @property
    def registration(self) -> ToolRegistration:
        return ToolRegistration(
            name="git_diff",
            description="Gets the git diff with argument injection and external execution protection.",
            input_schema={
                "type": "object",
                "properties": {
                    "file": {"type": "string", "description": "Optional file path to diff"},
                    "staged": {"type": "boolean", "description": "Optional flag to diff staged changes"}
                },
                "additionalProperties": False
            }
        )

    async def execute(self, arguments: Dict[str, Any], trace_id: str) -> Any:
        args = ["diff", "--no-ext-diff", "--no-textconv"]
        if arguments.get("staged"):
            args.append("--staged")
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
                },
                "additionalProperties": False
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

        return await self._run_git_command("log", f"-n{limit}", "--oneline")
