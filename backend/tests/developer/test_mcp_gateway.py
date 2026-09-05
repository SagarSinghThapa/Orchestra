import pytest
import asyncio
from typing import Any, Dict

from app.developer.mcp.gateway import MCPGateway
from app.developer.mcp.tools.base import BaseTool
from app.developer.schemas import ToolRegistration, ToolRequest, ToolResponseStatus
from app.developer.errors import InternalError


class DummyTool(BaseTool):
    @property
    def registration(self) -> ToolRegistration:
        return ToolRegistration(
            name="dummy",
            description="A dummy tool",
            input_schema={
                "type": "object",
                "properties": {
                    "arg": {"type": "string"}
                },
                "required": ["arg"]
            }
        )

    async def execute(self, arguments: Dict[str, Any], trace_id: str) -> Any:
        return f"Hello {arguments['arg']}"


class TimeoutTool(BaseTool):
    @property
    def registration(self) -> ToolRegistration:
        return ToolRegistration(
            name="timeout_tool",
            description="A tool that sleeps",
            input_schema={"type": "object"}
        )

    async def execute(self, arguments: Dict[str, Any], trace_id: str) -> Any:
        await asyncio.sleep(2.0)
        return "Done"


@pytest.mark.asyncio
async def test_mcp_gateway_success():
    gateway = MCPGateway()
    gateway.register_tool(DummyTool())
    
    req = ToolRequest(tool_name="dummy", arguments={"arg": "world"}, request_id="123")
    res = await gateway.dispatch(req)
    
    assert res.status == ToolResponseStatus.SUCCESS
    assert res.result == "Hello world"


@pytest.mark.asyncio
async def test_mcp_gateway_schema_validation_error():
    gateway = MCPGateway()
    gateway.register_tool(DummyTool())
    
    # Missing required 'arg'
    req = ToolRequest(tool_name="dummy", arguments={}, request_id="123")
    res = await gateway.dispatch(req)
    
    assert res.status == ToolResponseStatus.ERROR
    assert res.error_code == "E1xx"
    assert "Invalid arguments:" in res.result


@pytest.mark.asyncio
async def test_mcp_gateway_timeout():
    gateway = MCPGateway(execution_timeout_seconds=0.1)
    gateway.register_tool(TimeoutTool())
    
    req = ToolRequest(tool_name="timeout_tool", arguments={}, request_id="123")
    res = await gateway.dispatch(req)
    
    assert res.status == ToolResponseStatus.ERROR
    assert res.error_code == "E4xx"
