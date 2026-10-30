import os
import pytest
from pathlib import Path

from app.developer.errors import ValidationError
from app.developer.mcp.servers.filesystem import (
    ListFilesTool,
    ReadFileTool,
    WriteFileTool,
)
from app.developer.mcp.servers.git import GitDiffTool, GitLogTool
from app.developer.mcp.utils.sandbox import resolve_safe_path


@pytest.fixture
def temp_workspace(tmp_path: Path):
    ws = tmp_path / "sandbox_ws"
    ws.mkdir()
    # Create safe baseline file
    safe_file = ws / "safe.txt"
    safe_file.write_text("Hello Orchestra Sandbox!", encoding="utf-8")
    return ws


# 1. Path Traversal Penetration Vectors
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "traversal_payload",
    [
        "../../etc/passwd",
        "..\\..\\windows\\win.ini",
        "nested/../../outside.txt",
        "foo/..\\..\\bar.txt",
        "a/b/c/../../../../root.txt",
        "sub/dir/../../../../etc/shadow",
    ],
)
async def test_path_traversal_penetration(temp_workspace: Path, traversal_payload: str):
    # Test resolve_safe_path boundary
    with pytest.raises(ValidationError) as exc_info:
        resolve_safe_path(temp_workspace, traversal_payload)
    assert "traversal" in str(exc_info.value).lower() or "outside" in str(exc_info.value).lower()

    # Test actual tool execution boundary (ReadFileTool)
    read_tool = ReadFileTool(str(temp_workspace))
    with pytest.raises(ValidationError):
        await read_tool.execute({"path": traversal_payload}, trace_id="sec_test")


# 2. Windows Drive and UNC Path Escapes
@pytest.mark.parametrize(
    "drive_unc_payload",
    [
        "C:\\Windows\\System32\\cmd.exe",
        "C:autoexec.bat",
        "D:\\secrets\\keys.pem",
        "\\\\attacker-server\\share\\malware",
        "//192.168.1.1/c$/exploit",
    ],
)
def test_drive_and_unc_penetration(temp_workspace: Path, drive_unc_payload: str):
    with pytest.raises(ValidationError) as exc_info:
        resolve_safe_path(temp_workspace, drive_unc_payload)
    assert any(w in str(exc_info.value).lower() for w in ["unc", "outside", "drive", "prohibited"])


# 3. Alternate Data Stream (ADS) Penetration
@pytest.mark.parametrize(
    "ads_payload",
    [
        "safe.txt:hidden_stream",
        "code.py::$DATA",
        "nested/data.json:stream2",
    ],
)
def test_alternate_data_stream_penetration(temp_workspace: Path, ads_payload: str):
    with pytest.raises(ValidationError) as exc_info:
        resolve_safe_path(temp_workspace, ads_payload)
    assert "alternate data stream" in str(exc_info.value).lower() or ":" in str(exc_info.value)


# 4. Windows Reserved System Device Names
@pytest.mark.parametrize(
    "device_payload",
    [
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM9",
        "LPT1",
        "LPT9",
        "con.txt",
        "aux.json",
        "nul.py",
        "CON ",
        "prn.",
    ],
)
def test_windows_reserved_device_names(temp_workspace: Path, device_payload: str):
    with pytest.raises(ValidationError) as exc_info:
        resolve_safe_path(temp_workspace, device_payload)
    assert "reserved" in str(exc_info.value).lower()


# 5. Sensitive File Access Blocklist
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sensitive_target",
    [
        ".env",
        ".env.local",
        ".env.production",
        ".env.development",
        "id_rsa",
        "id_ed25519",
        "credentials.json",
        "service-account.json",
        ".git/config",
        ".ssh/authorized_keys",
        ".aws/credentials",
    ],
)
async def test_sensitive_credential_blocklist(temp_workspace: Path, sensitive_target: str):
    # Attempting to resolve with block_sensitive=True must fail
    with pytest.raises(ValidationError) as exc_info:
        resolve_safe_path(temp_workspace, sensitive_target, block_sensitive=True)
    assert "sensitive" in str(exc_info.value).lower()

    # Tool execution write attempt must fail
    write_tool = WriteFileTool(str(temp_workspace))
    with pytest.raises(ValidationError):
        await write_tool.execute({"path": sensitive_target, "content": "LEAKED_KEY=123"}, trace_id="sec_test")


# 6. Null-byte Injection Guard
def test_null_byte_injection(temp_workspace: Path):
    with pytest.raises(ValidationError) as exc_info:
        resolve_safe_path(temp_workspace, "safe.txt\0.exe")
    assert "null" in str(exc_info.value).lower()


# 7. Symlink Traversal Escape Containment
def test_symlink_escape_containment(temp_workspace: Path, tmp_path: Path):
    outside_file = tmp_path / "outside_target.txt"
    outside_file.write_text("OUTSIDE_SECRET_DATA", encoding="utf-8")

    link_path = temp_workspace / "symlink_escape.txt"
    try:
        link_path.symlink_to(outside_file)
    except (OSError, NotImplementedError):
        pytest.skip("Windows OS privilege does not permit unprivileged symlink creation")

    # Accessing symlink that resolves outside workspace root must be rejected
    with pytest.raises(ValidationError) as exc_info:
        resolve_safe_path(temp_workspace, "symlink_escape.txt")
    assert "symlink" in str(exc_info.value).lower() or "outside" in str(exc_info.value).lower()


# 8. Git Subprocess Argument Injection Guard
@pytest.mark.asyncio
async def test_git_diff_argument_injection(temp_workspace: Path):
    diff_tool = GitDiffTool(str(temp_workspace))
    # Disallow flag injection via file
    with pytest.raises(ValidationError) as exc_info:
        await diff_tool.execute({"file": "--output=/tmp/pwn"}, trace_id="sec_test")
    assert any(w in str(exc_info.value).lower() for w in ["flag", "invalid", "option", "prefix", "format", "dash"])


@pytest.mark.asyncio
async def test_git_log_limit_bounding(temp_workspace: Path):
    log_tool = GitLogTool(str(temp_workspace))
    # Negative limits or absurd limits must be rejected
    with pytest.raises(ValidationError):
        await log_tool.execute({"limit": -5}, trace_id="sec_test")
    with pytest.raises(ValidationError):
        await log_tool.execute({"limit": 1000}, trace_id="sec_test")
