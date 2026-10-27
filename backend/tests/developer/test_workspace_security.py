import os
import sys
from pathlib import Path
import pytest
from pydantic import ValidationError as PydanticValidationError

from app.developer.workspace import WorkspaceResolver
from app.developer.mcp.utils.sandbox import resolve_safe_path
from app.developer.errors import ValidationError
from app.developer.schemas import (
    DeveloperRequest,
    DeveloperResponse,
    DeveloperMode,
    TaskType,
    TaskStatus,
    ProposedPatch,
)


# =====================================================================
# 1. WorkspaceResolver Tests
# =====================================================================

def test_workspace_resolver_deterministic_mapping(tmp_path):
    resolver = WorkspaceResolver(base_dir=tmp_path)
    
    path_1 = resolver.resolve_project_workspace(1)
    path_2 = resolver.resolve_project_workspace(2)
    
    assert path_1 == tmp_path.resolve() / "project_1"
    assert path_2 == tmp_path.resolve() / "project_2"
    assert path_1 != path_2


def test_workspace_resolver_invalid_project_id(tmp_path):
    resolver = WorkspaceResolver(base_dir=tmp_path)
    with pytest.raises(ValidationError):
        resolver.resolve_project_workspace(0)
    with pytest.raises(ValidationError):
        resolver.resolve_project_workspace(-5)


def test_workspace_resolver_ensure_workspace(tmp_path):
    resolver = WorkspaceResolver(base_dir=tmp_path)
    path = resolver.ensure_workspace(10)
    assert path.is_dir()
    assert path == tmp_path.resolve() / "project_10"


def test_workspace_resolver_override_registration(tmp_path):
    resolver = WorkspaceResolver(base_dir=tmp_path)
    custom = tmp_path / "custom_repo"
    custom.mkdir()
    
    resolver.register_override(99, custom)
    assert resolver.resolve_project_workspace(99) == custom.resolve()
    
    resolver.clear_overrides()
    assert resolver.resolve_project_workspace(99) == tmp_path.resolve() / "project_99"


# =====================================================================
# 2. Windows Path & Boundary Security Tests
# =====================================================================

def test_resolve_safe_path_valid_relative(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    
    resolved = resolve_safe_path(root, "src/app.py")
    assert resolved == root.resolve() / "src" / "app.py"


def test_resolve_safe_path_rejects_parent_traversal(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    
    with pytest.raises(ValidationError) as exc:
        resolve_safe_path(root, "../outside.txt")
    assert "Path traversal detected" in exc.value.message


def test_resolve_safe_path_rejects_null_bytes(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    
    with pytest.raises(ValidationError) as exc:
        resolve_safe_path(root, "test\0.py")
    assert "null bytes" in exc.value.message


def test_resolve_safe_path_rejects_unc_paths(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    
    for unc in ["\\\\server\\share\\file.py", "//server/share/file.py"]:
        with pytest.raises(ValidationError) as exc:
            resolve_safe_path(root, unc)
        assert "UNC paths are prohibited" in exc.value.message


def test_resolve_safe_path_rejects_drive_letters(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    
    # Drive relative
    with pytest.raises(ValidationError) as exc:
        resolve_safe_path(root, "C:foo.txt")
    assert "prohibited" in exc.value.message

    # Foreign absolute drive
    foreign = "Z:\\secret.txt" if not str(root).startswith("Z:") else "Y:\\secret.txt"
    with pytest.raises(ValidationError) as exc:
        resolve_safe_path(root, foreign)
    assert "prohibited" in exc.value.message or "Path traversal" in exc.value.message


def test_resolve_safe_path_rejects_ads_colon(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    
    with pytest.raises(ValidationError) as exc:
        resolve_safe_path(root, "file.txt:stream")
    assert "Alternate Data Stream" in exc.value.message


def test_resolve_safe_path_rejects_windows_device_names(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    
    devices = ["CON", "PRN", "AUX", "NUL", "COM1", "COM9", "LPT1", "LPT9", "CON.txt", "NUL.py", "aux.log"]
    for dev in devices:
        with pytest.raises(ValidationError) as exc:
            resolve_safe_path(root, dev)
        assert "reserved system name" in exc.value.message


def test_resolve_safe_path_trailing_dots_and_spaces(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    
    # Normalizing trailing dots and spaces to prevent Win32 bypass
    with pytest.raises(ValidationError) as exc:
        resolve_safe_path(root, ".env.")
    assert "Access to sensitive file" in exc.value.message or "prohibited" in exc.value.message

    with pytest.raises(ValidationError) as exc:
        resolve_safe_path(root, ".env ")
    assert "Access to sensitive file" in exc.value.message or "prohibited" in exc.value.message

    with pytest.raises(ValidationError) as exc:
        resolve_safe_path(root, "NUL. ")
    assert "reserved system name" in exc.value.message


def test_resolve_safe_path_case_insensitive_sensitive_files(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    
    sensitive_targets = [
        ".ENV",
        ".Env.Local",
        ".git/CONFIG",
        "ID_RSA",
        "cert.PEM",
        "credentials.JSON",
        "sub/.env.production",
        "dir/.ssh/id_ed25519"
    ]
    
    for target in sensitive_targets:
        with pytest.raises(ValidationError) as exc:
            resolve_safe_path(root, target)
        assert "prohibited" in exc.value.message


def test_resolve_safe_path_symlink_containment(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("classified", encoding="utf-8")

    link = root / "link_out"
    try:
        os.symlink(str(outside), str(link), target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not permitted in this OS/user environment")

    # Accessing file through symlink pointing outside
    with pytest.raises(ValidationError) as exc:
        resolve_safe_path(root, "link_out/secret.txt")
    assert "Symlink traversal detected" in exc.value.message


# =====================================================================
# 3. Developer Schemas Validation Tests
# =====================================================================

def test_developer_request_valid():
    req = DeveloperRequest(
        task_type=TaskType.CODE_GEN,
        prompt="Refactor payment logic",
        target_files=["src/payment.py"],
        mode=DeveloperMode.PREVIEW,
    )
    assert req.task_type == TaskType.CODE_GEN
    assert req.prompt == "Refactor payment logic"
    assert req.mode == DeveloperMode.PREVIEW
    assert req.target_files == ["src/payment.py"]


def test_developer_request_forbids_extra_fields():
    with pytest.raises(PydanticValidationError):
        DeveloperRequest(
            task_type=TaskType.CODE_GEN,
            prompt="Refactor",
            system_prompt="malicious system prompt",  # forbidden
        )


def test_developer_request_bounds_prompt_length():
    with pytest.raises(PydanticValidationError):
        DeveloperRequest(
            task_type=TaskType.CODE_GEN,
            prompt="",  # min_length=1
        )
    with pytest.raises(PydanticValidationError):
        DeveloperRequest(
            task_type=TaskType.CODE_GEN,
            prompt="A" * 4001,  # max_length=4000
        )


def test_developer_response_serialization():
    patch = ProposedPatch(
        path="src/payment.py",
        diff="--- a\n+++ b\n",
        validation_status="validated_python_ast",
        original_hash="abc",
        new_hash="def",
        applied=False,
    )
    res = DeveloperResponse(
        status=TaskStatus.SUCCESS,
        task_type=TaskType.CODE_GEN,
        mode=DeveloperMode.PREVIEW,
        summary="Generated proposed patch",
        files_analyzed=["src/payment.py"],
        proposed_patches=[patch],
        warnings=[],
        tool_events=[],
        metadata={"duration_ms": 120.0},
    )
    assert res.status == TaskStatus.SUCCESS
    assert len(res.proposed_patches) == 1
    assert res.proposed_patches[0].path == "src/payment.py"
