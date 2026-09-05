import pytest
from pydantic import ValidationError as PydanticValidationError

from app.developer.schemas import (
    DeveloperTaskInput,
    DeveloperTaskOutput,
    TaskType,
    TaskStatus,
    ToolRegistration,
    ToolRequest,
    ToolResponse,
    ToolResponseStatus,
)
from app.developer.errors import ValidationError, AuthError, ErrorTaxonomy


def test_developer_task_input_valid():
    task = DeveloperTaskInput(
        task_type=TaskType.REPO_ANALYSIS,
        repo_ref="github.com/test/repo",
        params={"depth": 2}
    )
    assert task.task_type == TaskType.REPO_ANALYSIS
    assert task.repo_ref == "github.com/test/repo"
    assert task.params["depth"] == 2


def test_developer_task_input_invalid_type():
    with pytest.raises(PydanticValidationError):
        DeveloperTaskInput(
            task_type="invalid_type",
            repo_ref="github.com/test/repo",
        )


def test_developer_task_output_valid():
    output = DeveloperTaskOutput(
        result={"summary": "done"},
        artifacts=["file1.py"],
        status=TaskStatus.SUCCESS
    )
    assert output.status == TaskStatus.SUCCESS
    assert output.artifacts == ["file1.py"]


def test_mcp_tool_registration_valid():
    reg = ToolRegistration(
        name="test_tool",
        description="A test tool",
        input_schema={"type": "object", "properties": {"arg1": {"type": "string"}}}
    )
    assert reg.name == "test_tool"


def test_mcp_tool_request_valid():
    req = ToolRequest(
        tool_name="test_tool",
        arguments={"arg1": "value"},
        request_id="req-123"
    )
    assert req.tool_name == "test_tool"
    assert req.request_id == "req-123"


def test_mcp_tool_response_valid():
    res = ToolResponse(
        status=ToolResponseStatus.SUCCESS,
        result={"message": "ok"}
    )
    assert res.status == ToolResponseStatus.SUCCESS


def test_mcp_tool_response_error():
    res = ToolResponse(
        status=ToolResponseStatus.ERROR,
        error_code=ErrorTaxonomy.VALIDATION_INPUT.value
    )
    assert res.status == ToolResponseStatus.ERROR
    assert res.error_code == "E1xx"


def test_error_taxonomy_serialization():
    try:
        raise ValidationError("Invalid input data")
    except ValidationError as e:
        assert e.code == ErrorTaxonomy.VALIDATION_INPUT
        assert e.code.value == "E1xx"

