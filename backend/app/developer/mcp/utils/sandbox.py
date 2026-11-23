import os
import re
from pathlib import Path, PureWindowsPath
from typing import List, Set, Union

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
WINDOWS_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
SEPARATOR_SPLIT = re.compile(r"[/\\]+")


def _is_reparse_or_symlink(path: Path) -> bool:
    """Checks for POSIX symlinks or Windows NTFS junctions/reparse points without resolving."""
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if callable(is_junction):
        try:
            return bool(is_junction())
        except OSError:
            return True
    return False


def _validate_sensitive_segment(segment: str) -> None:
    """Enforces sensitive directory/file/extension blocklist on a single path segment."""
    part_norm = segment.rstrip(". ").lower()
    if not part_norm or part_norm == ".":
        return
    if part_norm in BLOCKED_SENSITIVE_DIRS:
        raise ValidationError(f"Access to sensitive directory '{segment}' is prohibited.")
    if (
        part_norm in BLOCKED_SENSITIVE_FILES
        or part_norm.startswith(".env")
        or part_norm == ".env"
    ):
        raise ValidationError(f"Access to sensitive file '{segment}' is prohibited.")
    if part_norm.endswith((".pem", ".key", ".pfx", ".p12", ".pkcs12")):
        raise ValidationError(f"Access to secret/key file '{segment}' is prohibited.")


def _validate_and_split_segments(raw_target: Union[str, Path], block_sensitive: bool) -> List[str]:
    """
    Performs host-independent lexical path validation BEFORE filesystem resolution.
    Treats both '/' and '\\' as path separators on all operating systems so Windows
    traversal, drive-letter, UNC, ADS, and reserved-name payloads cannot bypass on POSIX.
    """
    if raw_target is None:
        raise ValidationError("Invalid path format: path cannot be None.")

    raw_str = str(raw_target)

    # 1. Null-byte injection check (check raw string before trimming whitespace)
    if "\0" in raw_str:
        raise ValidationError("Invalid path format: contains null bytes.")

    path_str = raw_str.strip()

    # Empty or explicit current-directory reference resolves safely to workspace root
    if not path_str or path_str == ".":
        return []

    # 2. UNC / network / extended device path check across all slash combinations (\\, //, \/, /\)
    if len(path_str) >= 2 and path_str[0] in ("/", "\\") and path_str[1] in ("/", "\\"):
        raise ValidationError("Invalid path format: UNC paths are prohibited.")

    # 3. Host-independent Windows drive & drive-relative syntax check (e.g. C:\..., C:/..., C:foo)
    win_target = PureWindowsPath(path_str)
    if win_target.drive or WINDOWS_DRIVE_PREFIX.match(path_str):
        drive_label = win_target.drive or path_str[:2]
        raise ValidationError(
            f"Invalid path format: absolute or drive-scoped paths ('{drive_label}') outside workspace are prohibited."
        )

    # 4. Reject POSIX or Windows root-anchored absolute paths (e.g. /etc/passwd, \Windows\System32)
    if path_str.startswith(("/", "\\")):
        raise ValidationError(
            f"Invalid path format: absolute paths ('{raw_target}') outside workspace are prohibited."
        )

    # 5. Explicitly split across BOTH '/' and '\' regardless of host OS
    raw_segments = SEPARATOR_SPLIT.split(path_str)
    clean_parts: List[str] = []

    for seg in raw_segments:
        if not seg or seg == ".":
            continue

        # Reject parent traversal ('..', '.. ') and dot/space-only obfuscated segments ('...')
        stripped_edge = seg.strip()
        stripped_win32 = seg.rstrip(". ")
        if (
            seg == ".."
            or stripped_edge == ".."
            or (len(seg.rstrip(" ")) >= 2 and set(seg.rstrip(" ")) == {"."})
            or not stripped_win32
        ):
            raise ValidationError(
                f"Path traversal detected: '{raw_target}' is outside or traverses workspace boundaries."
            )

        # Reject Alternate Data Streams (colon syntax)
        if ":" in seg:
            raise ValidationError(f"Invalid path: Alternate Data Stream syntax detected in '{seg}'.")

        # Reject Windows reserved device names (with Win32 trailing dot/space normalization)
        if WINDOWS_RESERVED_NAMES.match(stripped_win32):
            raise ValidationError(f"Invalid path: contains reserved system name '{seg}'.")

        # Enforce sensitive file/directory blocklist lexically as well as post-resolution
        if block_sensitive:
            _validate_sensitive_segment(seg)

        clean_parts.append(seg)

    return clean_parts


def resolve_safe_path(
    workspace_root: Union[str, Path],
    target_path: Union[str, Path],
    block_sensitive: bool = True
) -> Path:
    """
    Resolves the target path against the workspace root and ensures it is strictly contained within it.
    Prevents path traversal (across both POSIX '/' and Windows '\\' separators), null-byte injection,
    absolute paths, UNC paths, Alternate Data Streams (ADS), Windows drive escapes,
    Windows reserved device names, symlink/junction escapes (including ancestors and dangling links),
    trailing dot/space Win32 normalizations, and sensitive file access.

    Raises:
        ValidationError (E1xx) if the path attempts traversal or touches sensitive/invalid targets.
    """
    # 1-5. Host-independent lexical validation before touching the filesystem
    clean_parts = _validate_and_split_segments(target_path, block_sensitive=block_sensitive)

    # 6. Resolve authoritative workspace root
    try:
        root_path = Path(workspace_root).resolve(strict=False)
    except Exception as e:
        raise ValidationError(f"Invalid workspace root format: {e}")

    # 7. Construct un-resolved candidate path and inspect existing components for symlinks/junctions
    # BEFORE calling .resolve() on the full target so escaped symlinks preserve symlink error taxonomy.
    candidate_path = root_path
    for idx, part in enumerate(clean_parts):
        candidate_path = candidate_path / part
        if _is_reparse_or_symlink(candidate_path):
            try:
                resolved_link = candidate_path.resolve(strict=False)
                resolved_link.relative_to(root_path)
            except Exception:
                if idx < len(clean_parts) - 1:
                    raise ValidationError(
                        "Symlink traversal detected: ancestor directory points outside workspace root."
                    )
                raise ValidationError(
                    "Symlink traversal detected: target is outside workspace root."
                )

    # 8. Resolve candidate path and enforce strict workspace containment boundary
    try:
        full_path = candidate_path.resolve(strict=False)
    except Exception as e:
        raise ValidationError(f"Invalid path resolution: {e}")

    try:
        rel_path = full_path.relative_to(root_path)
    except ValueError:
        raise ValidationError(f"Path traversal detected: '{target_path}' is outside the allowed workspace root.")

    # 9. Post-resolution symlink/reparse containment defense (handles resolved ancestors)
    curr = full_path
    while not curr.exists() and curr != root_path and curr != curr.parent:
        curr = curr.parent
    if curr.exists():
        try:
            curr_real = curr.resolve(strict=True)
            curr_real.relative_to(root_path)
        except Exception:
            raise ValidationError("Symlink traversal detected: ancestor directory points outside workspace root.")

    if full_path.exists():
        try:
            real_path = full_path.resolve(strict=True)
            real_path.relative_to(root_path)
        except Exception:
            raise ValidationError("Symlink traversal detected: target is outside workspace root.")

    # 10. Post-resolution sensitive files and directories check (catches internal symlinks aliasing secrets)
    if block_sensitive and rel_path != Path("."):
        for part in rel_path.parts:
            _validate_sensitive_segment(part)

    return full_path
