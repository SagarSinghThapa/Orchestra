import asyncio
import json
import time
from typing import Dict, List, Set, Optional

from jsonschema import validate, ValidationError as JsonSchemaValidationError

from app.developer.schemas import ToolRequest, ToolResponse, ToolResponseStatus, ToolEventRecord
from app.developer.errors import ErrorTaxonomy, DeveloperBaseException, ValidationError, TimeoutError, InternalError
from app.developer.mcp.tools.base import BaseTool
from app.developer.logging import StructuredLogger, scrub_secrets

MAX_MCP_ARGUMENT_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB payload limit

CANONICAL_DEVELOPER_TOOLS: Set[str] = {
    "read_file", "list_files", "search_files", "write_file",
    "repo_tree", "file_metadata", "search_code",
    "git_status", "git_diff", "git_log"
}

# Approved tool allowlist including test fixtures
ALLOWED_TOOL_NAMES: Set[str] = CANONICAL_DEVELOPER_TOOLS | {"dummy", "timeout_tool"}


class MCPGateway:
    """
    The MCP Gateway that manages tool registration and dispatching.
    Includes static tool allowlisting, JSON schema validation, execution timeouts,
    argument size checks, tool event tracing, and structured logging.
    """
    def __init__(self, execution_timeout_seconds: float = 30.0, allowed_tools: Optional[Set[str]] = None):
        self._tools: Dict[str, BaseTool] = {}
        self.logger = StructuredLogger("mcp-gateway")
        self.execution_timeout_seconds = execution_timeout_seconds
        self.allowed_tools = allowed_tools or ALLOWED_TOOL_NAMES
        self.events: List[ToolEventRecord] = []

        # Request-local execution and file budgets
        self.max_tool_calls: int = 20
        self.max_files_read: int = 10
        self.max_cumulative_read_bytes: int = 5 * 1024 * 1024
        self.max_files_modified: int = 5
        self.tool_calls_count: int = 0
        self.files_read: Set[str] = set()
        self.cumulative_read_bytes: int = 0
        self.files_modified: Set[str] = set()

    def register_tool(self, tool: BaseTool) -> None:
        """
        Registers a tool instance after verifying it belongs to the approved allowlist
        and enforces schema constraints.
        """
        reg = tool.registration
        if reg.name not in self.allowed_tools:
            raise ValidationError(f"Tool '{reg.name}' is not in the approved developer tool allowlist.")

        # Ensure additionalProperties: false is set for object schemas
        if isinstance(reg.input_schema, dict) and reg.input_schema.get("type") == "object":
            if "additionalProperties" not in reg.input_schema:
                reg.input_schema["additionalProperties"] = False

        self._tools[reg.name] = tool
        self.logger.info(f"Registered tool: {reg.name}", context={"schema": reg.input_schema})

    async def dispatch(self, request: ToolRequest) -> ToolResponse:
        """
        Dispatches a ToolRequest to the appropriate tool, applying JSON schema validation,
        timeouts, argument payload limits, structured event recording, and robust error handling.
        """
        trace_id = request.request_id
        tool_name = request.tool_name
        start_time = time.perf_counter()
        
        self.logger.info(f"Dispatching tool request: {tool_name}", trace_id=trace_id)

        # Check tool call budget: max 20 tool calls per request. 21st tool call is rejected.
        if self.tool_calls_count >= self.max_tool_calls:
            self._record_event(tool_name, None, start_time, "error")
            return ToolResponse(
                status=ToolResponseStatus.ERROR,
                error_code=ErrorTaxonomy.VALIDATION_INPUT.value,
                result=f"Tool call budget exceeded: maximum {self.max_tool_calls} tool calls allowed per request."
            )
        self.tool_calls_count += 1

        # 1. Validate argument types
        if not isinstance(request.arguments, dict):
            self._record_event(tool_name, None, start_time, "error")
            return ToolResponse(
                status=ToolResponseStatus.ERROR,
                error_code=ErrorTaxonomy.VALIDATION_INPUT.value,
                result="Invalid arguments: arguments must be a dictionary/object."
            )

        # 2. Validate payload size
        try:
            arg_bytes = len(json.dumps(request.arguments).encode("utf-8"))
            if arg_bytes > MAX_MCP_ARGUMENT_SIZE_BYTES:
                self._record_event(tool_name, None, start_time, "error")
                return ToolResponse(
                    status=ToolResponseStatus.ERROR,
                    error_code=ErrorTaxonomy.VALIDATION_INPUT.value,
                    result=f"Tool argument payload ({arg_bytes} bytes) exceeds maximum allowable limit ({MAX_MCP_ARGUMENT_SIZE_BYTES} bytes)."
                )
        except Exception as e:
            self._record_event(tool_name, None, start_time, "error")
            return ToolResponse(
                status=ToolResponseStatus.ERROR,
                error_code=ErrorTaxonomy.VALIDATION_INPUT.value,
                result=f"Failed to serialize arguments for size validation: {e}"
            )

        if tool_name not in self._tools:
            self.logger.warn(f"Tool not found or unapproved: {tool_name}", trace_id=trace_id)
            self._record_event(tool_name, None, start_time, "error")
            return ToolResponse(
                status=ToolResponseStatus.ERROR,
                error_code=ErrorTaxonomy.VALIDATION_INPUT.value,
                result=f"Tool not registered or unapproved: {tool_name}"
            )
        tool = self._tools[tool_name]
        target_path = str(request.arguments.get("path", "")) if "path" in request.arguments else None

        # 3. Validate arguments against the JSON Schema
        try:
            validate(instance=request.arguments, schema=tool.registration.input_schema)
        except JsonSchemaValidationError as e:
            self.logger.warn(f"Schema validation failed: {e.message}", trace_id=trace_id)
            self._record_event(tool_name, target_path, start_time, "error")
            return ToolResponse(
                status=ToolResponseStatus.ERROR,
                error_code=ErrorTaxonomy.VALIDATION_INPUT.value,
                result=f"Invalid arguments: {e.message}"
            )

        # Check file read and modify budgets before execution
        if tool_name == "read_file":
            if target_path and target_path not in self.files_read:
                if len(self.files_read) >= self.max_files_read:
                    self._record_event(tool_name, target_path, start_time, "error")
                    return ToolResponse(
                        status=ToolResponseStatus.ERROR,
                        error_code=ErrorTaxonomy.VALIDATION_INPUT.value,
                        result=f"File read limit exceeded: maximum {self.max_files_read} files may be read per request."
                    )
        elif tool_name == "write_file":
            if target_path and target_path not in self.files_modified:
                if len(self.files_modified) >= self.max_files_modified:
                    self._record_event(tool_name, target_path, start_time, "error")
                    return ToolResponse(
                        status=ToolResponseStatus.ERROR,
                        error_code=ErrorTaxonomy.VALIDATION_INPUT.value,
                        result=f"File modification limit exceeded: maximum {self.max_files_modified} files may be modified per request."
                    )

        # 4. Execute with timeout
        try:
            result = await asyncio.wait_for(
                tool.execute(request.arguments, trace_id=trace_id),
                timeout=self.execution_timeout_seconds
            )
            # Check cumulative read bytes and record touched files
            if tool_name == "read_file" and isinstance(result, str):
                read_bytes = len(result.encode("utf-8"))
                if self.cumulative_read_bytes + read_bytes > self.max_cumulative_read_bytes:
                    self._record_event(tool_name, target_path, start_time, "error")
                    return ToolResponse(
                        status=ToolResponseStatus.ERROR,
                        error_code=ErrorTaxonomy.VALIDATION_INPUT.value,
                        result=f"Cumulative read bytes limit exceeded: maximum {self.max_cumulative_read_bytes} bytes allowed."
                    )
                self.cumulative_read_bytes += read_bytes
                if target_path:
                    self.files_read.add(str(target_path))
            elif tool_name == "write_file" and target_path:
                self.files_modified.add(str(target_path))

            self.logger.info(f"Tool execution successful: {tool_name}", trace_id=trace_id)
            self._record_event(tool_name, target_path, start_time, "success")
            return ToolResponse(
                status=ToolResponseStatus.SUCCESS,
                result=result
            )
            
        except asyncio.TimeoutError:
            self.logger.error(f"Tool execution timed out: {tool_name}", trace_id=trace_id)
            self._record_event(tool_name, target_path, start_time, "error")
            return ToolResponse(
                status=ToolResponseStatus.ERROR,
                error_code=ErrorTaxonomy.TIMEOUT.value,
                result="Tool execution timed out."
            )
        except DeveloperBaseException as e:
            clean_msg = scrub_secrets(e.message)
            self.logger.warn(f"Tool logic error: {clean_msg}", trace_id=trace_id, context=e.context)
            self._record_event(tool_name, target_path, start_time, "error")
            return ToolResponse(
                status=ToolResponseStatus.ERROR,
                error_code=e.code.value,
                result=clean_msg
            )
        except Exception as e:
            clean_err = scrub_secrets(str(e))
            self.logger.error(f"Unhandled tool error: {clean_err}", trace_id=trace_id)
            self._record_event(tool_name, target_path, start_time, "error")
            return ToolResponse(
                status=ToolResponseStatus.ERROR,
                error_code=ErrorTaxonomy.INTERNAL.value,
                result=f"Internal tool error: {clean_err}"
            )

    def _record_event(self, tool_name: str, target_path: Optional[str], start_time: float, status: str) -> None:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        self.events.append(
            ToolEventRecord(
                tool_name=tool_name,
                target_path=target_path,
                duration_ms=round(duration_ms, 2),
                status=status
            )
        )
