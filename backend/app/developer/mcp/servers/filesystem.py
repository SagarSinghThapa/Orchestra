import asyncio
import hashlib
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Set, Optional

from app.developer.mcp.tools.base import BaseTool
from app.developer.schemas import ToolRegistration
from app.developer.mcp.utils.sandbox import resolve_safe_path
from app.developer.errors import InternalError, ValidationError

MAX_READ_FILE_BYTES = 1024 * 1024  # 1 MB limit
MAX_WRITE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB limit
MAX_DIRECTORY_ENTRIES = 500
MAX_SEARCH_RESULTS = 200
MAX_SEARCH_DEPTH = 10

BINARY_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp",
    ".pdf", ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".pyc", ".pyd",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp3", ".mp4", ".mov", ".avi", ".flac", ".wav", ".iso"
}

IGNORED_SEARCH_DIRS: Set[str] = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".next", "dist", "build"
}

# Registry for in-process per-workspace write locks to serialize concurrent writes
_WORKSPACE_LOCKS: Dict[str, asyncio.Lock] = {}


def get_workspace_lock(workspace_root: str) -> asyncio.Lock:
    canonical = str(Path(workspace_root).resolve())
    if canonical not in _WORKSPACE_LOCKS:
        _WORKSPACE_LOCKS[canonical] = asyncio.Lock()
    return _WORKSPACE_LOCKS[canonical]


class ReadFileTool(BaseTool):
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root

    @property
    def registration(self) -> ToolRegistration:
        return ToolRegistration(
            name="read_file",
            description="Reads the contents of a file safely with size and binary checks.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file relative to the workspace root."}
                },
                "required": ["path"],
                "additionalProperties": False
            }
        )

    async def execute(self, arguments: Dict[str, Any], trace_id: str) -> Any:
        target_path = resolve_safe_path(self.workspace_root, arguments["path"])
        if not target_path.is_file():
            raise InternalError(f"File not found: {arguments['path']}")

        # 1. Check binary extensions
        suffix = target_path.suffix.lower()
        if suffix in BINARY_EXTENSIONS:
            raise ValidationError(f"Cannot read binary file with extension '{suffix}'.")

        # 2. Check file size limits before reading
        try:
            file_size = target_path.stat().st_size
            if file_size > MAX_READ_FILE_BYTES:
                raise ValidationError(
                    f"File '{arguments['path']}' size ({file_size} bytes) exceeds maximum allowable limit ({MAX_READ_FILE_BYTES} bytes)."
                )
        except OSError as e:
            raise InternalError(f"Failed to inspect file stat: {e}")

        # 3. Detect binary content via null bytes in initial chunk
        try:
            with open(target_path, "rb") as bf:
                chunk = bf.read(512)
                if b"\x00" in chunk:
                    raise ValidationError(f"Cannot read binary file: null bytes detected in '{arguments['path']}'.")
        except OSError as e:
            raise InternalError(f"Failed to inspect file header: {e}")

        # 4. Safe UTF-8 read
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            raise ValidationError(f"Cannot read file '{arguments['path']}': file is not valid UTF-8 text.")
        except Exception as e:
            raise InternalError(f"Failed to read file: {e}")


class ListFilesTool(BaseTool):
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root

    @property
    def registration(self) -> ToolRegistration:
        return ToolRegistration(
            name="list_files",
            description="Lists files in a directory up to the maximum entry limit.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the directory relative to the workspace root."}
                },
                "required": ["path"],
                "additionalProperties": False
            }
        )

    async def execute(self, arguments: Dict[str, Any], trace_id: str) -> Any:
        target_path = resolve_safe_path(self.workspace_root, arguments["path"])
        if not target_path.is_dir():
            raise InternalError(f"Directory not found: {arguments['path']}")

        try:
            files = []
            count = 0
            for item in sorted(target_path.iterdir(), key=lambda p: p.name):
                if count >= MAX_DIRECTORY_ENTRIES:
                    break
                files.append({
                    "name": item.name,
                    "is_dir": item.is_dir(),
                    "size": item.stat().st_size if item.is_file() else None
                })
                count += 1
            return files
        except Exception as e:
            raise InternalError(f"Failed to list directory: {e}")


class SearchFilesTool(BaseTool):
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root

    @property
    def registration(self) -> ToolRegistration:
        return ToolRegistration(
            name="search_files",
            description="Searches for files by name with depth and result limits.",
            input_schema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Substring to search for in filenames."},
                    "path": {"type": "string", "description": "Directory to search in."}
                },
                "required": ["pattern"],
                "additionalProperties": False
            }
        )

    async def execute(self, arguments: Dict[str, Any], trace_id: str) -> Any:
        search_dir = arguments.get("path", "")
        target_path = resolve_safe_path(self.workspace_root, search_dir)
        pattern = arguments["pattern"]

        if not target_path.is_dir():
            raise InternalError(f"Directory not found: {search_dir}")

        matches = []
        base_depth = len(target_path.parts)

        for root, dirs, files in os.walk(target_path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d.lower() not in IGNORED_SEARCH_DIRS]

            current_depth = len(Path(root).parts) - base_depth
            if current_depth > MAX_SEARCH_DEPTH:
                dirs.clear()
                continue

            for file in sorted(files):
                if pattern in file:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, start=self.workspace_root)
                    matches.append(rel_path.replace("\\", "/"))
                    if len(matches) >= MAX_SEARCH_RESULTS:
                        return matches

        return matches


class WriteFileTool(BaseTool):
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root

    @property
    def registration(self) -> ToolRegistration:
        return ToolRegistration(
            name="write_file",
            description="Writes content to a file atomically with size limits and optimistic concurrency hash checks.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file relative to the workspace root."},
                    "content": {"type": "string", "description": "The file content to write."},
                    "expected_hash": {"type": ["string", "null"], "description": "Optional expected SHA-256 hex string of existing content for optimistic concurrency."}
                },
                "required": ["path", "content"],
                "additionalProperties": False
            }
        )

    async def execute(self, arguments: Dict[str, Any], trace_id: str) -> Any:
        content = arguments["content"]
        expected_hash = arguments.get("expected_hash")
        
        # Enforce max write size
        content_bytes = len(content.encode("utf-8"))
        if content_bytes > MAX_WRITE_SIZE_BYTES:
            raise ValidationError(
                f"Write content size ({content_bytes} bytes) exceeds maximum allowable limit ({MAX_WRITE_SIZE_BYTES} bytes)."
            )

        target_path = resolve_safe_path(self.workspace_root, arguments["path"])

        # Enforce in-process per-workspace lock around hash-check and atomic write sequence
        lock = get_workspace_lock(self.workspace_root)
        async with lock:
            target_existed = target_path.exists()
            original_hash = None

            if target_existed:
                original_hash = hashlib.sha256(target_path.read_bytes()).hexdigest()
                if expected_hash is not None and expected_hash.strip():
                    if original_hash.lower() != expected_hash.strip().lower():
                        raise ValidationError(
                            f"Optimistic concurrency failure for '{arguments['path']}': file was modified concurrently (hash mismatch)."
                        )
            else:
                if expected_hash is not None and expected_hash.strip():
                    raise ValidationError(
                        f"Optimistic concurrency failure for '{arguments['path']}': expected existing file was not found."
                    )

            # Ensure parent directories exist
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Atomic write via temporary file in the target directory followed by os.replace
            temp_filename = f".tmp.{uuid.uuid4().hex}.writing"
            temp_path = target_path.parent / temp_filename

            try:
                with open(temp_path, "w", encoding="utf-8") as f:
                    f.write(content)
                os.replace(temp_path, target_path)
            except Exception as e:
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except Exception:
                        pass
                raise InternalError(f"Failed to write file atomically: {e}")

            new_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

            return {
                "success": True,
                "path": arguments["path"],
                "original_hash": original_hash,
                "new_hash": new_hash
            }
