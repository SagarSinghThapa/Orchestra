from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    REPO_ANALYSIS = "repo_analysis"
    CODE_GEN = "code_gen"
    DOC_GEN = "doc_gen"


class TaskStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"


class DeveloperTaskInput(BaseModel):
    task_type: TaskType = Field(..., description="The type of developer task")
    repo_ref: str = Field(..., description="A reference to the repository")
    params: Dict[str, Any] = Field(default_factory=dict, description="Task specific parameters")


class DeveloperTaskOutput(BaseModel):
    result: Dict[str, Any] = Field(default_factory=dict, description="The execution result")
    artifacts: List[str] = Field(default_factory=list, description="List of generated artifact paths")
    status: TaskStatus = Field(..., description="Status of the task execution")


# MCP Protocol Schemas

class ToolRegistration(BaseModel):
    name: str = Field(..., description="Name of the MCP tool")
    description: str = Field(..., description="Description of what the tool does")
    input_schema: Dict[str, Any] = Field(..., description="JSONSchema defining tool arguments")


class ToolRequest(BaseModel):
    tool_name: str = Field(..., description="Name of the requested tool")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments to execute the tool with")
    request_id: str = Field(..., description="Unique ID for tracing the request")


class ToolResponseStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"


class ToolResponse(BaseModel):
    status: ToolResponseStatus = Field(..., description="Status of the tool execution")
    result: Any = Field(default=None, description="The output result of the tool")
    error_code: Optional[str] = Field(default=None, description="Error code matching the shared taxonomy if status is error")


class RepositoryAnalysisResult(BaseModel):
    repository: Dict[str, Any] = Field(default_factory=dict, description="Basic repository stats")
    languages: List[str] = Field(default_factory=list, description="Detected languages")
    frameworks: List[str] = Field(default_factory=list, description="Detected frameworks")
    architecture: Dict[str, Any] = Field(default_factory=dict, description="Architecture pattern inferences")
    important_files: List[str] = Field(default_factory=list, description="Crucial manifest and configuration paths")
    dependencies: List[str] = Field(default_factory=list, description="Key dependencies")
    entry_points: List[str] = Field(default_factory=list, description="Application entry points")
    modules: List[str] = Field(default_factory=list, description="High level modules")
    tests: Dict[str, Any] = Field(default_factory=dict, description="Test suite discovery")
    risks: List[str] = Field(default_factory=list, description="Identified technical risks")
    recommendations: List[str] = Field(default_factory=list, description="Agent recommendations for implementation")


class CodingAgentResult(BaseModel):
    summary: str = Field(..., description="Summary of actions taken or planned")
    plan: List[str] = Field(default_factory=list, description="List of implementation steps")
    files_changed: List[str] = Field(default_factory=list, description="List of file paths affected")
    diffs: Dict[str, str] = Field(default_factory=dict, description="Dictionary mapping file paths to unified diffs")
    validation: Dict[str, str] = Field(default_factory=dict, description="Dictionary mapping file paths to validation status/errors")
    warnings: List[str] = Field(default_factory=list, description="Any warnings such as size limits or invalid extensions")


class DocAgentResult(BaseModel):
    document_type: str = Field(..., description="The type of document generated")
    content: str = Field(..., description="The markdown content")
    sources: List[str] = Field(default_factory=list, description="Files and context inspected")
    artifact: Optional[str] = Field(default=None, description="Path where it was written if applied")
    warnings: List[str] = Field(default_factory=list, description="Warnings about missing verifiable info")



