import os
from pathlib import Path
from typing import Dict, Optional, Union

from app.core.config import settings
from app.developer.errors import ValidationError


class WorkspaceResolver:
    """
    Authoritative server-controlled workspace resolver.
    Deterministically maps database project_id to an isolated workspace directory
    under settings.workspace_base_dir. Client requests can never inject or override
    the root directory.
    """

    def __init__(self, base_dir: Optional[Union[str, Path]] = None):
        configured = base_dir or getattr(settings, "workspace_base_dir", "workspaces")
        self._base_dir = Path(configured).resolve()
        self._overrides: Dict[int, Path] = {}

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    def register_override(self, project_id: int, workspace_path: Union[str, Path]) -> None:
        """Server/test-controlled override registration. Never accessible via client input."""
        if not isinstance(project_id, int) or project_id <= 0:
            raise ValidationError(f"Invalid project_id: must be a positive integer, got {project_id}")
        resolved = Path(workspace_path).resolve()
        self._overrides[project_id] = resolved

    def clear_overrides(self) -> None:
        """Clear test overrides."""
        self._overrides.clear()

    def resolve_project_workspace(self, project_id: int) -> Path:
        """
        Deterministically resolves the canonical workspace path for a project.
        Ensures project_id cannot contain path traversal or drive syntax.
        """
        if not isinstance(project_id, int) or project_id <= 0:
            raise ValidationError(f"Invalid project_id: must be a positive integer, got {project_id}")

        if project_id in self._overrides:
            return self._overrides[project_id]

        workspace_path = self._base_dir / f"project_{project_id}"
        return workspace_path.resolve()

    def ensure_workspace(self, project_id: int) -> Path:
        """
        Resolves the canonical workspace path and ensures the directory exists on disk.
        """
        path = self.resolve_project_workspace(project_id)
        path.mkdir(parents=True, exist_ok=True)
        return path


# Default singleton instance
default_workspace_resolver = WorkspaceResolver()
