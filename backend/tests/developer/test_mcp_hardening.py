import asyncio
import hashlib
import os
import shutil
from pathlib import Path
import pytest

from app.developer.mcp.gateway import MCPGateway
from app.developer.mcp.servers.filesystem import ReadFileTool, WriteFileTool, ListFilesTool
from app.developer.mcp.servers.git import GitStatusTool, GitDiffTool, GitLogTool
from app.developer.mcp.tools.base import BaseTool
from app.developer.schemas import ToolRegistration, ToolRequest, ToolResponseStatus
from app.developer.errors import ValidationError, InternalError


class MaliciousTool(BaseTool):
    @property
    def registration(self) -> ToolRegistration:
        return ToolRegistration(
            name="arbitrary_exec",
            description="Unauthorized tool",
            input_schema={"type": "object", "properties": {"cmd": {"type": "string"}}}
        )

    async def execute(self, arguments, trace_id):
        return "pwned"


# =====================================================================
# 1. MCP Gateway Allowlist & Schema Tests
# =====================================================================

def test_gateway_rejects_unapproved_tool():
    gateway = MCPGateway()
    with pytest.raises(ValidationError) as exc:
        gateway.register_tool(MaliciousTool())
    assert "not in the approved developer tool allowlist" in exc.value.message


@pytest.mark.asyncio
async def test_gateway_rejects_additional_properties(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "test.txt").write_text("hello", encoding="utf-8")

    gateway = MCPGateway()
    gateway.register_tool(ReadFileTool(str(root)))

    # Extra property 'injected' should fail validation
    req = ToolRequest(
        tool_name="read_file",
        arguments={"path": "test.txt", "injected": "malicious"},
        request_id="req-add-prop"
    )
    res = await gateway.dispatch(req)
    assert res.status == ToolResponseStatus.ERROR
    assert "Invalid arguments" in res.result or "Additional properties are not allowed" in res.result


@pytest.mark.asyncio
async def test_gateway_records_tool_events(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "main.py").write_text("print(1)", encoding="utf-8")

    gateway = MCPGateway()
    gateway.register_tool(ReadFileTool(str(root)))

    req = ToolRequest(tool_name="read_file", arguments={"path": "main.py"}, request_id="trace-audit")
    res = await gateway.dispatch(req)
    assert res.status == ToolResponseStatus.SUCCESS

    assert len(gateway.events) == 1
    event = gateway.events[0]
    assert event.tool_name == "read_file"
    assert event.target_path == "main.py"
    assert event.status == "success"
    assert event.duration_ms >= 0.0


# =====================================================================
# 2. Git Upward Discovery & Environment Hardening Tests
# =====================================================================

@pytest.mark.asyncio
async def test_git_subprocess_rejects_non_git_workspace_without_walking_up(tmp_path):
    # A directory that is NOT a git repo (even if parent directory is a git repo)
    non_git_workspace = tmp_path / "isolated_project"
    non_git_workspace.mkdir()

    tool = GitStatusTool(str(non_git_workspace))
    with pytest.raises(ValidationError) as exc:
        await tool.execute({}, "trace-git-nogit")
    assert "Workspace is not a Git repository" in exc.value.message


@pytest.mark.asyncio
async def test_git_subprocess_sanitized_env(tmp_path):
    workspace = tmp_path / "git_repo"
    workspace.mkdir()
    # Fake a .git directory
    (workspace / ".git").mkdir()

    tool = GitStatusTool(str(workspace))
    env = tool._get_sanitized_environment()

    # Verify sensitive environment keys are absent
    assert "LLM_API_KEY" not in env
    assert "JWT_SECRET" not in env
    assert "DATABASE_URL" not in env
    assert "AWS_ACCESS_KEY_ID" not in env
    assert env.get("GIT_TERMINAL_PROMPT") == "0"
    assert env.get("GIT_CONFIG_NOSYSTEM") == "1"
    assert "GIT_CEILING_DIRECTORIES" in env


# =====================================================================
# 3. Atomic Write & Optimistic Concurrency Tests
# =====================================================================

@pytest.mark.asyncio
async def test_write_file_atomic_replacement(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()

    tool = WriteFileTool(str(root))
    res = await tool.execute({"path": "src/module.py", "content": "x = 1\n"}, "trace-write")

    assert res["success"] is True
    assert res["path"] == "src/module.py"
    target = root / "src" / "module.py"
    assert target.is_file()
    assert target.read_text(encoding="utf-8") == "x = 1\n"
    # Ensure no lingering temporary files
    tmp_files = list(target.parent.glob(".tmp.*"))
    assert len(tmp_files) == 0


@pytest.mark.asyncio
async def test_write_file_optimistic_concurrency_success(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    f = root / "code.py"
    f.write_bytes(b"version = 1\n")
    initial_hash = hashlib.sha256(b"version = 1\n").hexdigest()

    tool = WriteFileTool(str(root))
    res = await tool.execute({
        "path": "code.py",
        "content": "version = 2\n",
        "expected_hash": initial_hash
    }, "trace-opt-ok")

    assert res["success"] is True
    assert res["original_hash"] == initial_hash
    assert f.read_text(encoding="utf-8") == "version = 2\n"


@pytest.mark.asyncio
async def test_write_file_optimistic_concurrency_rejection(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    f = root / "code.py"
    f.write_text("concurrently changed\n", encoding="utf-8")
    stale_hash = hashlib.sha256(b"stale content\n").hexdigest()

    tool = WriteFileTool(str(root))
    with pytest.raises(ValidationError) as exc:
        await tool.execute({
            "path": "code.py",
            "content": "new version\n",
            "expected_hash": stale_hash
        }, "trace-opt-fail")

    assert "Optimistic concurrency failure" in exc.value.message
    # File content must remain unchanged
    assert f.read_text(encoding="utf-8") == "concurrently changed\n"


@pytest.mark.asyncio
async def test_write_file_concurrent_locking(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    f = root / "counter.txt"
    f.write_text("0", encoding="utf-8")

    tool = WriteFileTool(str(root))

    # Run two writes concurrently with the same original expected_hash
    h0 = hashlib.sha256(b"0").hexdigest()
    results = await asyncio.gather(
        tool.execute({"path": "counter.txt", "content": "1", "expected_hash": h0}, "t1"),
        tool.execute({"path": "counter.txt", "content": "2", "expected_hash": h0}, "t2"),
        return_exceptions=True
    )

    # One must succeed, and the other must fail with optimistic concurrency failure
    successes = [r for r in results if isinstance(r, dict) and r.get("success")]
    failures = [r for r in results if isinstance(r, ValidationError)]

    assert len(successes) == 1
    assert len(failures) == 1
    assert "Optimistic concurrency failure" in failures[0].message
