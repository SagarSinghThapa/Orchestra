import os
import re
from pathlib import Path
from typing import Any, Dict, Set

from app.developer.mcp.tools.base import BaseTool
from app.developer.schemas import ToolRegistration
from app.developer.mcp.utils.sandbox import resolve_safe_path
from app.developer.errors import InternalError, ValidationError

MAX_TREE_DEPTH = 6
MAX_TREE_LINES = 1000
MAX_REGEX_LENGTH = 100
MAX_CODE_SEARCH_MATCHES = 200
MAX_FILES_SCANNED = 500
MAX_LINE_LENGTH = 250

EXCLUDED_TREE_DIRS: Set[str] = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".next", "dist", "build", ".pytest_cache"
}

# Heuristic detector for obvious nested quantifiers that trigger catastrophic backtracking
SUSPICIOUS_NESTED_QUANTIFIERS = re.compile(r"(\([^\)]*[\*\+][^\)]*\))[\*\+]")


class RepoTreeTool(BaseTool):
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root

    @property
    def registration(self) -> ToolRegistration:
        return ToolRegistration(
            name="repo_tree",
            description="Generates a tree view of the repository directory with depth and line bounds.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Sub-directory to get tree for."}
                }
            }
        )

    async def execute(self, arguments: Dict[str, Any], trace_id: str) -> Any:
        search_dir = arguments.get("path", "")
        # Allow resolving empty string to root without blocking, but validate path
        target_path = resolve_safe_path(self.workspace_root, search_dir, block_sensitive=False)
        
        if not target_path.is_dir():
            raise InternalError(f"Directory not found: {search_dir}")
        
        tree = []
        base_depth = len(target_path.parts)

        for root, dirs, files in os.walk(target_path):
            # Prune ignored and hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d.lower() not in EXCLUDED_TREE_DIRS]
            
            level = len(Path(root).parts) - base_depth
            if level > MAX_TREE_DEPTH:
                dirs.clear()
                continue

            indent = ' ' * 4 * level
            tree.append(f"{indent}{os.path.basename(root)}/")
            if len(tree) >= MAX_TREE_LINES:
                tree.append("... [tree truncated: maximum line limit reached]")
                return "\n".join(tree)

            subindent = ' ' * 4 * (level + 1)
            for f in sorted(files):
                if f.startswith('.'):
                    continue
                tree.append(f"{subindent}{f}")
                if len(tree) >= MAX_TREE_LINES:
                    tree.append("... [tree truncated: maximum line limit reached]")
                    return "\n".join(tree)
                
        return "\n".join(tree)


class FileMetadataTool(BaseTool):
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root

    @property
    def registration(self) -> ToolRegistration:
        return ToolRegistration(
            name="file_metadata",
            description="Gets metadata for a specific file safely.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
                },
                "required": ["path"]
            }
        )

    async def execute(self, arguments: Dict[str, Any], trace_id: str) -> Any:
        target_path = resolve_safe_path(self.workspace_root, arguments["path"])
        if not target_path.exists():
            raise InternalError("Path does not exist.")
            
        try:
            stat = target_path.stat()
            return {
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "is_dir": target_path.is_dir()
            }
        except Exception as e:
            raise InternalError(f"Failed to inspect metadata: {e}")


class SearchCodeTool(BaseTool):
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root

    @property
    def registration(self) -> ToolRegistration:
        return ToolRegistration(
            name="search_code",
            description="Regex search across repository files with ReDoS and match limits.",
            input_schema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern (max 100 chars)"}
                },
                "required": ["pattern"]
            }
        )

    async def execute(self, arguments: Dict[str, Any], trace_id: str) -> Any:
        pattern = arguments["pattern"]
        if not isinstance(pattern, str):
            raise ValidationError("Search pattern must be a string.")

        if len(pattern) > MAX_REGEX_LENGTH:
            raise ValidationError(f"Search pattern length ({len(pattern)}) exceeds maximum limit ({MAX_REGEX_LENGTH}).")

        if SUSPICIOUS_NESTED_QUANTIFIERS.search(pattern):
            raise ValidationError("Regex pattern rejected: potential catastrophic backtracking detected.")

        try:
            regex = re.compile(pattern)
        except re.error as e:
            raise ValidationError(f"Invalid regex: {e}")

        results = []
        target_path = resolve_safe_path(self.workspace_root, "", block_sensitive=False)
        files_scanned = 0

        for root, dirs, files in os.walk(target_path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d.lower() not in EXCLUDED_TREE_DIRS]
            
            for file in files:
                if not file.endswith(('.py', '.js', '.ts', '.tsx', '.jsx', '.md', '.json', '.html', '.css', '.txt')):
                    continue

                files_scanned += 1
                if files_scanned > MAX_FILES_SCANNED:
                    return results

                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.workspace_root)
                
                # Check size before reading
                try:
                    if os.path.getsize(full_path) > 512 * 1024:  # Skip files > 512KB during regex scan
                        continue
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            if regex.search(line):
                                trimmed = line.strip()
                                if len(trimmed) > MAX_LINE_LENGTH:
                                    trimmed = trimmed[:MAX_LINE_LENGTH] + "..."
                                results.append({"file": rel_path, "line": line_num, "content": trimmed})
                                if len(results) >= MAX_CODE_SEARCH_MATCHES:
                                    return results
                except Exception:
                    continue

        return results

