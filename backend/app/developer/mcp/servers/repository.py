import os
import re
from typing import Any, Dict

from app.developer.mcp.tools.base import BaseTool
from app.developer.schemas import ToolRegistration
from app.developer.mcp.utils.sandbox import resolve_safe_path
from app.developer.errors import InternalError


class RepoTreeTool(BaseTool):
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root

    @property
    def registration(self) -> ToolRegistration:
        return ToolRegistration(
            name="repo_tree",
            description="Generates a tree view of the repository directory.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Sub-directory to get tree for."}
                }
            }
        )

    async def execute(self, arguments: Dict[str, Any], trace_id: str) -> Any:
        search_dir = arguments.get("path", "")
        target_path = resolve_safe_path(self.workspace_root, search_dir)
        
        if not target_path.is_dir():
            raise InternalError(f"Directory not found: {search_dir}")
        
        tree = []
        for root, dirs, files in os.walk(target_path):
            # Ignore hidden dirs like .git or .venv
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            level = root.replace(str(target_path), '').count(os.sep)
            indent = ' ' * 4 * (level)
            tree.append(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 4 * (level + 1)
            for f in files:
                tree.append(f"{subindent}{f}")
                
        return "\n".join(tree)


class FileMetadataTool(BaseTool):
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root

    @property
    def registration(self) -> ToolRegistration:
        return ToolRegistration(
            name="file_metadata",
            description="Gets metadata for a specific file.",
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
            
        stat = target_path.stat()
        return {
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "is_dir": target_path.is_dir()
        }


class SearchCodeTool(BaseTool):
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root

    @property
    def registration(self) -> ToolRegistration:
        return ToolRegistration(
            name="search_code",
            description="Regex search across the repository files.",
            input_schema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern"}
                },
                "required": ["pattern"]
            }
        )

    async def execute(self, arguments: Dict[str, Any], trace_id: str) -> Any:
        pattern = arguments["pattern"]
        try:
            regex = re.compile(pattern)
        except re.error as e:
            raise InternalError(f"Invalid regex: {e}")

        results = []
        target_path = resolve_safe_path(self.workspace_root, "")
        for root, dirs, files in os.walk(target_path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for file in files:
                # Naive text check
                if not file.endswith(('.py', '.js', '.ts', '.md', '.json', '.html', '.css', '.txt')):
                    continue
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.workspace_root)
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        for line_num, line in enumerate(f, 1):
                            if regex.search(line):
                                results.append({"file": rel_path, "line": line_num, "content": line.strip()})
                except UnicodeDecodeError:
                    pass
        return results
