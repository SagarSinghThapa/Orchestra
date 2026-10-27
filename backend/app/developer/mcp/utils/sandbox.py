import os
import re
from pathlib import Path, PureWindowsPath
from typing import Union, Set

from app.developer.errors import ValidationError

# Blocked filenames and extensions that may contain sensitive credentials or internal configs
BLOCKED_SENSITIVE_FILES: Set[str] = {
    ".env", ".env.local", ".env.production", ".env.development", ".env.staging",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "credentials.json",
    "service-account.json", "service-account-key.json", "authorized_keys", "known_hosts"
}

BLOCKED_SENSITIVE_DIRS: Set[str] = {
    ".git", ".ssh", ".aws", ".gnupg", ".azure", ".kube"
}

WINDOWS_RESERVED_NAMES = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?$", re.IGNORECASE)


def resolve_safe_path(
    workspace_root: Union[str, Path], 
    target_path: Union[str, Path],
    block_sensitive: bool = True
) -> Path:
    """
    Resolves the target path against the workspace root and ensures it is strictly contained within it.
    Prevents path traversal, null-byte injection, UNC paths, Alternate Data Streams (ADS),
    Windows drive escapes, Windows reserved device names, symlink/junction escapes,
    trailing dot/space Win32 normalizations, and sensitive file access.
    
    Raises:
        ValidationError (E1xx) if the path attempts traversal or touches sensitive/invalid targets.
    """
    path_str = str(target_path).strip()

    # 1. Null-byte injection check
    if "\0" in path_str:
        raise ValidationError("Invalid path format: contains null bytes.")

    # 2. UNC path check
    if path_str.startswith(("\\\\", "//")):
        raise ValidationError("Invalid path format: UNC paths are prohibited.")

    # 3. Check Windows drive syntax using PureWindowsPath
    win_target = PureWindowsPath(path_str)
    if win_target.drive:
        # Check if root has drive
        root_win = PureWindowsPath(str(workspace_root))
        if not path_str.startswith(str(workspace_root)):
            # If it's a drive-relative path (e.g. C:foo) or a different drive, reject
            raise ValidationError(f"Invalid path format: absolute or drive-scoped paths ('{win_target.drive}') outside workspace are prohibited.")

    # 4. Basic format validation
    try:
        root_path = Path(workspace_root).resolve(strict=False)
        target = Path(target_path)
    except Exception as e:
        raise ValidationError(f"Invalid path format: {e}")

    # 5. Check components for Alternate Data Streams (colon) and Windows reserved names
    for part in target.parts:
        if part not in (target.drive, root_path.drive) and ":" in part:
            raise ValidationError(f"Invalid path: Alternate Data Stream syntax detected in '{part}'.")

        # Win32 normalization: strip trailing dots and spaces before comparing
        norm_part = part.rstrip(". ")
        if norm_part and WINDOWS_RESERVED_NAMES.match(norm_part):
            raise ValidationError(f"Invalid path: contains reserved system name '{part}'.")

    # 6. Resolve safe full path
    try:
        if target.is_absolute():
            full_path = target.resolve(strict=False)
        else:
            full_path = root_path.joinpath(target).resolve(strict=False)
    except Exception as e:
        raise ValidationError(f"Invalid path resolution: {e}")

    # 7. Path traversal boundary check
    try:
        rel_path = full_path.relative_to(root_path)
    except ValueError:
        raise ValidationError(f"Path traversal detected: '{target_path}' is outside the allowed workspace root.")

    # 8. Symlink / Junction / Reparse-point containment check
    # Check nearest existing ancestor to prevent parent symlink escapes for new files
    curr = full_path
    while not curr.exists() and curr != root_path and curr != curr.parent:
        curr = curr.parent
    if curr.exists():
        try:
            curr_real = curr.resolve(strict=True)
            curr_real.relative_to(root_path)
        except ValueError:
            raise ValidationError("Symlink traversal detected: ancestor directory points outside workspace root.")

    if full_path.exists():
        try:
            real_path = full_path.resolve(strict=True)
            real_path.relative_to(root_path)
        except ValueError:
            raise ValidationError("Symlink traversal detected: target is outside workspace root.")

    # 9. Sensitive files and directories check
    if block_sensitive and rel_path != Path("."):
        for part in rel_path.parts:
            part_norm = part.rstrip(". ").lower()
            if part_norm in BLOCKED_SENSITIVE_DIRS:
                raise ValidationError(f"Access to sensitive directory '{part}' is prohibited.")
            if (
                part_norm in BLOCKED_SENSITIVE_FILES
                or part_norm.startswith(".env")
                or part_norm == ".env"
            ):
                raise ValidationError(f"Access to sensitive file '{part}' is prohibited.")
            if part_norm.endswith((".pem", ".key", ".pfx", ".p12", ".pkcs12")):
                raise ValidationError(f"Access to secret/key file '{part}' is prohibited.")

    return full_path
