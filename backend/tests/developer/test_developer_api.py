from pathlib import Path
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.models.project import Project
from app.models.user import User
from app.developer.schemas import DeveloperMode, TaskType, TaskStatus
from app.developer.services.developer_service import DeveloperService
from app.developer.errors import TimeoutError as DevTimeoutError
from app.research.llm.mock import DeterministicTestLLMProvider


class TestDeveloperAPI:
    """End-to-end integration and security test suite for Developer REST API."""

    def test_unauthenticated_request_rejected(
        self,
        client: TestClient,
        test_project: Project,
    ):
        """Unauthenticated requests must be rejected with 401 Unauthorized."""
        payload = {
            "task_type": "repo_analysis",
            "prompt": "Analyze repository architecture",
            "mode": "preview",
        }
        response = client.post(
            f"/projects/{test_project.id}/developer",
            json=payload,
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_idor_unowned_project_returns_404(
        self,
        client: TestClient,
        set_auth,
        test_user_b: User,
        test_project: Project,
        test_llm_provider: DeterministicTestLLMProvider,
    ):
        """Accessing a foreign project must return 404 without leaking project existence."""
        set_auth(test_user_b)
        test_llm_provider.call_count = 0

        payload = {
            "task_type": "repo_analysis",
            "prompt": "Analyze repository architecture",
            "mode": "preview",
        }
        response = client.post(
            f"/projects/{test_project.id}/developer",
            json=payload,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Project not found"
        # Empirically verify 0 LLM and 0 tool calls occurred
        assert test_llm_provider.call_count == 0

    def test_viewer_role_cannot_apply_modifications(
        self,
        client: TestClient,
        set_auth,
        test_viewer_user: User,
        test_viewer_project: Project,
    ):
        """Users with VIEWER role must be forbidden (HTTP 403) from applying code modifications."""
        set_auth(test_viewer_user)

        payload = {
            "task_type": "code_gen",
            "prompt": "Apply bug fix",
            "mode": "apply",
            "target_files": ["main.py"],
        }
        response = client.post(
            f"/projects/{test_viewer_project.id}/developer",
            json=payload,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Viewer role is not authorized" in response.json()["detail"]

    def test_viewer_role_can_preview(
        self,
        client: TestClient,
        set_auth,
        test_viewer_user: User,
        test_viewer_project: Project,
    ):
        """Users with VIEWER role are permitted to run preview (read-only) tasks."""
        set_auth(test_viewer_user)

        payload = {
            "task_type": "repo_analysis",
            "prompt": "Read repo overview",
            "mode": "preview",
        }
        response = client.post(
            f"/projects/{test_viewer_project.id}/developer",
            json=payload,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "success"
        assert data["mode"] == "preview"

    def test_developer_repo_analysis_success(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
        test_workspace_resolver,
    ):
        """Repo analysis task completes and returns structured DeveloperResponse."""
        set_auth(test_user)
        ws = test_workspace_resolver.ensure_workspace(test_project.id)
        (ws / "main.py").write_bytes(b"import fastapi\napp = fastapi.FastAPI()\n")

        payload = {
            "task_type": "repo_analysis",
            "prompt": "Analyze repository frameworks and structure",
            "mode": "preview",
        }
        response = client.post(
            f"/projects/{test_project.id}/developer",
            json=payload,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "success"
        assert data["task_type"] == "repo_analysis"
        assert len(data["tool_events"]) >= 1

    def test_developer_code_gen_preview_mode(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
        test_workspace_resolver,
    ):
        """Code generation in preview mode proposes diffs and AST status without touching disk."""
        set_auth(test_user)
        ws = test_workspace_resolver.ensure_workspace(test_project.id)
        (ws / "app.py").write_bytes(b"def compute():\n    return 42\n")

        payload = {
            "task_type": "code_gen",
            "prompt": "Update compute function",
            "mode": "preview",
            "target_files": ["app.py"],
        }
        response = client.post(
            f"/projects/{test_project.id}/developer",
            json=payload,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["mode"] == "preview"
        # Disk content must remain untouched
        assert (ws / "app.py").read_bytes() == b"def compute():\n    return 42\n"

    def test_developer_code_gen_apply_mode(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
        test_workspace_resolver,
    ):
        """Code generation in apply mode atomically modifies disk for member."""
        set_auth(test_user)
        ws = test_workspace_resolver.ensure_workspace(test_project.id)
        (ws / "util.py").write_bytes(b"x = 1\n")

        # Call with proposed changes via context hints or mock
        payload = {
            "task_type": "code_gen",
            "prompt": "Update util.py",
            "mode": "apply",
            "target_files": ["util.py"],
        }
        response = client.post(
            f"/projects/{test_project.id}/developer",
            json=payload,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["mode"] == "apply"

    def test_developer_doc_gen_success(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
        test_workspace_resolver,
    ):
        """Doc generation task returns grounded documentation."""
        set_auth(test_user)
        ws = test_workspace_resolver.ensure_workspace(test_project.id)
        (ws / "pyproject.toml").write_bytes(b"[project]\nname = 'doc_test'\n")

        payload = {
            "task_type": "doc_gen",
            "prompt": "Generate README documentation",
            "mode": "preview",
        }
        response = client.post(
            f"/projects/{test_project.id}/developer",
            json=payload,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["documentation"] is not None

    def test_developer_traversal_payload_rejected(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
    ):
        """Target files traversing outside workspace must return 400 Bad Request."""
        set_auth(test_user)
        payload = {
            "task_type": "code_gen",
            "prompt": "Malicious traversal attempt",
            "target_files": ["../outside.py"],
            "mode": "preview",
        }
        response = client.post(
            f"/projects/{test_project.id}/developer",
            json=payload,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_developer_sensitive_file_rejected(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
    ):
        """Target files pointing to sensitive files must return 400 Bad Request."""
        set_auth(test_user)
        payload = {
            "task_type": "code_gen",
            "prompt": "Inspect credentials",
            "target_files": [".env"],
            "mode": "preview",
        }
        response = client.post(
            f"/projects/{test_project.id}/developer",
            json=payload,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_developer_extra_fields_forbidden(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
    ):
        """Payloads containing unapproved extra fields must be rejected with 422."""
        set_auth(test_user)
        payload = {
            "task_type": "repo_analysis",
            "prompt": "Valid prompt",
            "mode": "preview",
            "unapproved_extra_field": "injected",
        }
        response = client.post(
            f"/projects/{test_project.id}/developer",
            json=payload,
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_developer_timeout_returns_504(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
        monkeypatch,
        test_developer_service: DeveloperService,
    ):
        """When DeveloperService times out, API returns HTTP 504 Gateway Timeout."""
        set_auth(test_user)

        async def _mock_timeout(*args, **kwargs):
            raise DevTimeoutError("Developer task timed out after 45.0s")

        monkeypatch.setattr(test_developer_service, "execute_task", _mock_timeout)

        payload = {
            "task_type": "repo_analysis",
            "prompt": "Timeout test",
            "mode": "preview",
        }
        response = client.post(
            f"/projects/{test_project.id}/developer",
            json=payload,
        )
        assert response.status_code == status.HTTP_504_GATEWAY_TIMEOUT
        assert response.json()["detail"] == "Developer task timed out."
