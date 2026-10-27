from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TaskType(str, Enum):
    REPO_ANALYSIS = "repo_analysis"
    CODE_GEN = "code_gen"
    DOC_GEN = "doc_gen"


class TaskStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"


class DeveloperMode(str, Enum):
    PREVIEW = "preview"
    APPLY = "apply"


class DeveloperTaskInput(BaseModel):
    task_type: TaskType = Field(..., description="The type of developer task")
    repo_ref: str = Field(..., description="A reference to the repository")
    params: Dict[str, Any] = Field(default_factory=dict, description="Task specific parameters")


class DeveloperTaskOutput(BaseModel):
    result: Dict[str, Any] = Field(default_factory=dict, description="The execution result")
    artifacts: List[str] = Field(default_factory=list, description="List of generated artifact paths")
    status: TaskStatus = Field(..., description="Status of the task execution")


# Canonical Production Schemas (Phase 07)

class ProposedPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(..., description="Target relative file path within workspace")
    diff: str = Field(..., description="Unified diff of proposed changes")
    validation_status: str = Field(..., description="AST or syntax validation result")
    original_hash: Optional[str] = Field(default=None, description="SHA-256 hash before patch")
    new_hash: Optional[str] = Field(default=None, description="SHA-256 hash after patch")
    applied: bool = Field(default=False, description="Whether the patch was written to disk")


class ToolEventRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(..., description="Name of the invoked tool")
    target_path: Optional[str] = Field(default=None, description="Relative target path")
    duration_ms: float = Field(..., description="Execution duration in milliseconds")
    status: str = Field(..., description="success or error")


class DeveloperRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_type: TaskType = Field(..., description="The type of developer task")
    prompt: str = Field(..., min_length=1, max_length=4000, description="Task instruction prompt")
    target_files: Optional[List[str]] = Field(default=None, max_length=10, description="Optional target file paths relative to workspace")
    mode: DeveloperMode = Field(default=DeveloperMode.PREVIEW, description="preview (dry run) or apply (modify disk)")
    expected_file_hashes: Optional[Dict[str, str]] = Field(default=None, description="Optional relative-path to SHA-256 map for optimistic concurrency")
    context_hints: Optional[Dict[str, str]] = Field(default=None, description="Optional key-value metadata hints (e.g. doc_type)")


class DeveloperResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: TaskStatus = Field(..., description="Task execution status")
    task_type: TaskType = Field(..., description="The type of developer task")
    mode: DeveloperMode = Field(..., description="preview or apply mode")
    summary: str = Field(..., description="High-level narrative of actions taken or planned")
    files_analyzed: List[str] = Field(default_factory=list, description="List of files read or inspected")
    proposed_patches: List[ProposedPatch] = Field(default_factory=list, description="List of structured patch artifacts")
    documentation: Optional[str] = Field(default=None, description="Generated markdown documentation")
    warnings: List[str] = Field(default_factory=list, description="Diagnostic and validation warnings")
    tool_events: List[ToolEventRecord] = Field(default_factory=list, description="Structured tool audit events")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Performance and call metrics")


# MCP Protocol Schemas

class ToolRegistration(BaseModel):
    name: str = Field(..., description="Name of the MCP tool")
    description: str = Field(..., description="Description of what the tool does")
    input_schema: Dict[str, Any] = Field(..., description="JSONSchema defining tool arguments")


class ToolRequest(BaseModel):
    tool_name: str = Field(..., description="Name of the requested tool")
    arguments: Any = Field(default_factory=dict, description="Arguments to execute the tool with")
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
    proposed_patches: List[Dict[str, Any]] = Field(default_factory=list, description="Structured patch list")


class DocAgentResult(BaseModel):
    document_type: str = Field(..., description="The type of document generated")
    content: str = Field(..., description="The markdown content")
    sources: List[str] = Field(default_factory=list, description="Files and context inspected")
    artifact: Optional[str] = Field(default=None, description="Path where it was written if applied")
    warnings: List[str] = Field(default_factory=list, description="Warnings about missing verifiable info")
