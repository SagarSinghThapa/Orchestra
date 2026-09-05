import os
from typing import Any, Dict

from app.developer.mcp.tools.base import BaseTool
from app.developer.schemas import ToolRegistration
from app.developer.mcp.utils.sandbox import resolve_safe_path
from app.developer.errors import InternalError


class ReadFileTool(BaseTool):
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root

    @property
    def registration(self) -> ToolRegistration:
        return ToolRegistration(
            name="read_file",
            description="Reads the contents of a file.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file relative to the workspace root."}
                },
                "required": ["path"]
            }
        )

    async def execute(self, arguments: Dict[str, Any], trace_id: str) -> Any:
        target_path = resolve_safe_path(self.workspace_root, arguments["path"])
        if not target_path.is_file():
            raise InternalError(f"File not found: {arguments['path']}")
        
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            raise InternalError("Cannot read binary files.")
        except Exception as e:
            raise InternalError(f"Failed to read file: {e}")


class ListFilesTool(BaseTool):
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root

    @property
    def registration(self) -> ToolRegistration:
        return ToolRegistration(
            name="list_files",
            description="Lists files in a directory.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the directory relative to the workspace root."}
                },
                "required": ["path"]
            }
        )

    async def execute(self, arguments: Dict[str, Any], trace_id: str) -> Any:
        target_path = resolve_safe_path(self.workspace_root, arguments["path"])
        if not target_path.is_dir():
            raise InternalError(f"Directory not found: {arguments['path']}")
        
        try:
            files = []
            for item in target_path.iterdir():
                files.append({
                    "name": item.name,
                    "is_dir": item.is_dir(),
                    "size": item.stat().st_size if item.is_file() else None
                })
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
            description="Searches for files by name using simple matching.",
            input_schema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Substring to search for in filenames."},
                    "path": {"type": "string", "description": "Directory to search in."}
                },
                "required": ["pattern"]
            }
        )

    async def execute(self, arguments: Dict[str, Any], trace_id: str) -> Any:
        # Defaults to workspace root if no path provided
        search_dir = arguments.get("path", "")
        target_path = resolve_safe_path(self.workspace_root, search_dir)
        pattern = arguments["pattern"]

        if not target_path.is_dir():
            raise InternalError(f"Directory not found: {search_dir}")
        
        matches = []
        for root, _, files in os.walk(target_path):
            for file in files:
                if pattern in file:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, start=self.workspace_root)
                    matches.append(rel_path)
        
        return matches


class WriteFileTool(BaseTool):
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root

    @property
    def registration(self) -> ToolRegistration:
        return ToolRegistration(
            name="write_file",
            description="Writes content to a file, overwriting if it exists.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file relative to the workspace root."},
                    "content": {"type": "string", "description": "The file content to write."}
                },
                "required": ["path", "content"]
            }
        )

    async def execute(self, arguments: Dict[str, Any], trace_id: str) -> Any:
        target_path = resolve_safe_path(self.workspace_root, arguments["path"])
        
        # Ensure parent directories exist
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(arguments["content"])
            return {"success": True, "path": arguments["path"]}
        except Exception as e:
            raise InternalError(f"Failed to write file: {e}")

