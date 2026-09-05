import os
from pathlib import Path
from typing import Union

from app.developer.errors import ValidationError


def resolve_safe_path(workspace_root: Union[str, Path], target_path: Union[str, Path]) -> Path:
    """
    Resolves the target path against the workspace root and ensures it is contained within it.
    Prevents path traversal vulnerabilities.
    
    Raises:
        ValidationError (E1xx) if the path attempts to traverse outside the workspace root.
    """
    try:
        root_path = Path(workspace_root).resolve(strict=False)
        # Using joinpath safely resolves relative to root
        full_path = root_path.joinpath(target_path).resolve(strict=False)
    except Exception as e:
        raise ValidationError(f"Invalid path format: {e}")

    try:
        # Check if full_path is relative to root_path (i.e. contained within it)
        full_path.relative_to(root_path)
    except ValueError:
        raise ValidationError(f"Path traversal detected: {target_path} is outside the allowed workspace root.")

    return full_path
