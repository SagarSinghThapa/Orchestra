import os
from pathlib import Path
import pytest
from app.core.config import settings
from app.evaluations.service import EvaluationService


def test_resolve_git_sha_settings_override(monkeypatch):
    """Verifies that settings.app_git_sha takes highest precedence."""
    monkeypatch.setattr(settings, "app_git_sha", "settings_sha_123")
    monkeypatch.setenv("APP_GIT_SHA", "env_sha_456")
    sha = EvaluationService.resolve_git_sha()
    assert sha == "settings_sha_123"


def test_resolve_git_sha_env_var_override(monkeypatch):
    """Verifies that APP_GIT_SHA environment variable takes precedence when settings is None."""
    monkeypatch.setattr(settings, "app_git_sha", None)
    monkeypatch.setenv("APP_GIT_SHA", "env_override_999")
    sha = EvaluationService.resolve_git_sha()
    assert sha == "env_override_999"


def test_resolve_git_sha_symbolic_head(tmp_path, monkeypatch):
    """Verifies that symbolic ref: refs/heads/develop resolves target ref commit SHA."""
    monkeypatch.setattr(settings, "app_git_sha", None)
    monkeypatch.delenv("APP_GIT_SHA", raising=False)

    git_dir = tmp_path / ".git"
    git_dir.mkdir(parents=True)
    head_file = git_dir / "HEAD"
    head_file.write_text("ref: refs/heads/develop\n", encoding="utf-8")

    ref_file = git_dir / "refs" / "heads" / "develop"
    ref_file.parent.mkdir(parents=True)
    ref_file.write_text("abcdef1234567890abcdef1234567890abcdef12\n", encoding="utf-8")

    sha = EvaluationService.resolve_git_sha(repo_root_override=tmp_path)
    assert sha == "abcdef123456"


def test_resolve_git_sha_packed_refs(tmp_path, monkeypatch):
    """Verifies that packed-refs is parsed if loose ref file does not exist."""
    monkeypatch.setattr(settings, "app_git_sha", None)
    monkeypatch.delenv("APP_GIT_SHA", raising=False)

    git_dir = tmp_path / ".git"
    git_dir.mkdir(parents=True)
    head_file = git_dir / "HEAD"
    head_file.write_text("ref: refs/heads/main\n", encoding="utf-8")

    packed_refs = git_dir / "packed-refs"
    packed_refs.write_text(
        "# pack-refs with: peeled-tags inline\n"
        "fedcba6543210987fedcba6543210987fedcba65 refs/heads/main\n",
        encoding="utf-8",
    )

    sha = EvaluationService.resolve_git_sha(repo_root_override=tmp_path)
    assert sha == "fedcba654321"


def test_resolve_git_sha_detached_head(tmp_path, monkeypatch):
    """Verifies that detached HEAD containing raw commit SHA is read directly."""
    monkeypatch.setattr(settings, "app_git_sha", None)
    monkeypatch.delenv("APP_GIT_SHA", raising=False)

    git_dir = tmp_path / ".git"
    git_dir.mkdir(parents=True)
    head_file = git_dir / "HEAD"
    head_file.write_text("11223344556677889900aabbccddeeff11223344\n", encoding="utf-8")

    sha = EvaluationService.resolve_git_sha(repo_root_override=tmp_path)
    assert sha == "112233445566"


def test_resolve_git_sha_missing_git(tmp_path, monkeypatch):
    """Verifies that a directory without .git returns 'development' fallback."""
    monkeypatch.setattr(settings, "app_git_sha", None)
    monkeypatch.delenv("APP_GIT_SHA", raising=False)

    sha = EvaluationService.resolve_git_sha(repo_root_override=tmp_path)
    assert sha == "development"


def test_resolve_git_sha_malformed_head(tmp_path, monkeypatch):
    """Verifies that a malformed HEAD returns 'development' fallback safely."""
    monkeypatch.setattr(settings, "app_git_sha", None)
    monkeypatch.delenv("APP_GIT_SHA", raising=False)

    git_dir = tmp_path / ".git"
    git_dir.mkdir(parents=True)
    head_file = git_dir / "HEAD"
    head_file.write_text("??? not a ref or sha ???\n", encoding="utf-8")

    sha = EvaluationService.resolve_git_sha(repo_root_override=tmp_path)
    assert sha == "development"


def test_resolve_git_sha_live_repository(monkeypatch):
    """Verifies that running in live repository returns actual commit SHA."""
    monkeypatch.setattr(settings, "app_git_sha", None)
    monkeypatch.delenv("APP_GIT_SHA", raising=False)

    sha = EvaluationService.resolve_git_sha()
    assert len(sha) == 12
    assert sha != "development"
    assert all(c in "0123456789abcdef" for c in sha)
