import os
import re
from pathlib import Path
from typing import Union, Set

from app.developer.errors import ValidationError

# Blocked filenames and extensions that may contain sensitive credentials or internal configs
BLOCKED_SENSITIVE_FILES: Set[str] = {
    ".env", ".env.local", ".env.production", ".env.development", ".env.staging",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "credentials.json"
}

BLOCKED_SENSITIVE_DIRS: Set[str] = {
    ".git", ".ssh", ".aws", ".gnupg"
}

WINDOWS_RESERVED_NAMES = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?$", re.IGNORECASE)


def resolve_safe_path(
    workspace_root: Union[str, Path], 
    target_path: Union[str, Path],
    block_sensitive: bool = True
) -> Path:
    """
    Resolves the target path against the workspace root and ensures it is contained within it.
    Prevents path traversal, null-byte injection, Windows reserved names, and sensitive file access.
    
    Raises:
        ValidationError (E1xx) if the path attempts traversal or touches sensitive/invalid targets.
    """
    path_str = str(target_path).strip()

    # 1. Null-byte injection check
    if "\0" in path_str:
        raise ValidationError("Invalid path format: contains null bytes.")

    # 2. Basic format validation
    try:
        root_path = Path(workspace_root).resolve(strict=False)
        target = Path(target_path)
    except Exception as e:
        raise ValidationError(f"Invalid path format: {e}")

    # 3. Check Windows reserved device names in components
    for part in target.parts:
        if WINDOWS_RESERVED_NAMES.match(part):
            raise ValidationError(f"Invalid path: contains reserved system name '{part}'.")

    # 4. Resolve safe full path
    try:
        # If target is absolute on Windows or Unix, joinpath might reset root;
        # so we strip leading drive/slashes when interpreting as relative to workspace
        if target.is_absolute():
            # Check if it was already explicitly rooted in workspace_root
            full_path = target.resolve(strict=False)
        else:
            full_path = root_path.joinpath(target).resolve(strict=False)
    except Exception as e:
        raise ValidationError(f"Invalid path resolution: {e}")

    # 5. Path traversal boundary check
    try:
        rel_path = full_path.relative_to(root_path)
    except ValueError:
        raise ValidationError(f"Path traversal detected: '{target_path}' is outside the allowed workspace root.")

    # 6. Sensitive files and directories check
    if block_sensitive and rel_path != Path("."):
        for part in rel_path.parts:
            part_lower = part.lower()
            if part_lower in BLOCKED_SENSITIVE_DIRS:
                raise ValidationError(f"Access to sensitive directory '{part}' is prohibited.")
            if part_lower in BLOCKED_SENSITIVE_FILES or part_lower.startswith(".env."):
                raise ValidationError(f"Access to sensitive file '{part}' is prohibited.")
            if part_lower.endswith((".pem", ".key", ".pfx", ".p12", ".pkcs12")):
                raise ValidationError(f"Access to secret/key file '{part}' is prohibited.")

    return full_path

