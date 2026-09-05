import asyncio
from typing import Dict

from jsonschema import validate, ValidationError as JsonSchemaValidationError

from app.developer.schemas import ToolRequest, ToolResponse, ToolResponseStatus
from app.developer.errors import ErrorTaxonomy, DeveloperBaseException, ValidationError, TimeoutError, InternalError
from app.developer.mcp.tools.base import BaseTool
from app.developer.logging import StructuredLogger


class MCPGateway:
    """
    The MCP Gateway that manages tool registration and dispatching.
    Includes JSON schema validation, timeouts, and structured logging.
    """
    def __init__(self, execution_timeout_seconds: float = 30.0):
        self._tools: Dict[str, BaseTool] = {}
        self.logger = StructuredLogger("mcp-gateway")
        self.execution_timeout_seconds = execution_timeout_seconds

    def register_tool(self, tool: BaseTool) -> None:
        """
        Registers a tool instance.
        """
        reg = tool.registration
        self._tools[reg.name] = tool
        self.logger.info(f"Registered tool: {reg.name}", context={"schema": reg.input_schema})

    async def dispatch(self, request: ToolRequest) -> ToolResponse:
        """
        Dispatches a ToolRequest to the appropriate tool, applying JSON schema validation,
        timeouts, and robust error handling.
        """
        trace_id = request.request_id
        tool_name = request.tool_name
        
        self.logger.info(f"Dispatching tool request: {tool_name}", trace_id=trace_id)

        if tool_name not in self._tools:
            self.logger.warn(f"Tool not found: {tool_name}", trace_id=trace_id)
            return ToolResponse(
                status=ToolResponseStatus.ERROR,
                error_code=ErrorTaxonomy.VALIDATION_INPUT.value,
                result=f"Tool not registered: {tool_name}"
            )
        
        tool = self._tools[tool_name]
        
        # Validate arguments against the JSON Schema
        try:
            validate(instance=request.arguments, schema=tool.registration.input_schema)
        except JsonSchemaValidationError as e:
            self.logger.warn(f"Schema validation failed: {e.message}", trace_id=trace_id)
            return ToolResponse(
                status=ToolResponseStatus.ERROR,
                error_code=ErrorTaxonomy.VALIDATION_INPUT.value,
                result=f"Invalid arguments: {e.message}"
            )

        # Execute with timeout
        try:
            result = await asyncio.wait_for(
                tool.execute(request.arguments, trace_id=trace_id),
                timeout=self.execution_timeout_seconds
            )
            self.logger.info(f"Tool execution successful: {tool_name}", trace_id=trace_id)
            return ToolResponse(
                status=ToolResponseStatus.SUCCESS,
                result=result
            )
            
        except asyncio.TimeoutError:
            self.logger.error(f"Tool execution timed out: {tool_name}", trace_id=trace_id)
            return ToolResponse(
                status=ToolResponseStatus.ERROR,
                error_code=ErrorTaxonomy.TIMEOUT.value,
                result="Tool execution timed out."
            )
        except DeveloperBaseException as e:
            # Re-raise or capture expected taxonomy errors (like Validation for path traversal)
            self.logger.warn(f"Tool logic error: {e.message}", trace_id=trace_id, context=e.context)
            return ToolResponse(
                status=ToolResponseStatus.ERROR,
                error_code=e.code.value,
                result=e.message
            )
        except Exception as e:
            # Catch-all for unhandled internal errors
            self.logger.error(f"Unhandled tool error: {str(e)}", trace_id=trace_id)
            return ToolResponse(
                status=ToolResponseStatus.ERROR,
                error_code=ErrorTaxonomy.INTERNAL.value,
                result=f"Internal tool error: {str(e)}"
            )
