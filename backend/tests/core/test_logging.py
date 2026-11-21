import io
import json
import logging
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.context import set_request_id, reset_request_id
from app.core.logging import (
    OrchestraJsonFormatter,
    StructuredLogger,
    scrub_secrets,
)
from app.core.middleware import RequestIDMiddleware, StructuredLoggingMiddleware


def test_scrub_secrets_comprehensive():
    # 1. JWT token
    jwt = "eyJhGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    scrubbed = scrub_secrets(f"Token is {jwt}")
    assert "[REDACTED_JWT]" in scrubbed
    assert jwt not in scrubbed

    # 2. Bearer token
    bearer = "Bearer ya29.a0AfH6SMAxyz-1234567890abcdef"
    scrubbed = scrub_secrets(f"Header: {bearer}")
    assert "Bearer [REDACTED_TOKEN]" in scrubbed
    assert "ya29" not in scrubbed

    # 3. OpenAI API key
    sk = "sk-1234567890abcdef1234567890abcdef"
    scrubbed = scrub_secrets(f"Key: {sk}")
    assert "sk-[REDACTED_KEY]" in scrubbed
    assert sk not in scrubbed

    # 4. GitHub token
    ghp = "ghp_1234567890abcdef1234567890abcdef"
    scrubbed = scrub_secrets(f"GitHub: {ghp}")
    assert "gh_[REDACTED_TOKEN]" in scrubbed
    assert ghp not in scrubbed

    # 5. AWS Key
    aws = "AKIA1234567890ABCDEF"
    scrubbed = scrub_secrets(f"AWS: {aws}")
    assert "AKIA[REDACTED_AWS]" in scrubbed
    assert aws not in scrubbed

    # 6. Sensitive dictionary keys
    data = {
        "password": "supersecretpassword",
        "api_key": "raw_api_key",
        "normal_field": "hello world",
        "nested": {
            "token": "nested_secret",
            "safe": 12345
        }
    }
    scrubbed_dict = scrub_secrets(data)
    assert scrubbed_dict["password"] == "[REDACTED]"
    assert scrubbed_dict["api_key"] == "[REDACTED]"
    assert scrubbed_dict["normal_field"] == "hello world"
    assert scrubbed_dict["nested"]["token"] == "[REDACTED]"
    assert scrubbed_dict["nested"]["safe"] == 12345


def test_orchestra_json_formatter():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    formatter = OrchestraJsonFormatter()
    handler.setFormatter(formatter)

    test_logger = logging.getLogger("test.json.formatter")
    test_logger.handlers = [handler]
    test_logger.setLevel(logging.INFO)
    test_logger.propagate = False

    token = set_request_id("req_formatter_test_123")
    try:
        test_logger.info("Executing step sk-abcdef123456789012345678")
    finally:
        reset_request_id(token)

    output = stream.getvalue().strip()
    assert output, "Expected log record to be emitted"
    record = json.loads(output)
    assert record["request_id"] == "req_formatter_test_123"
    assert record["level"] == "INFO"
    assert "timestamp" in record
    assert "sk-[REDACTED_KEY]" in record["message"]
    assert "sk-abcdef" not in record["message"]


def test_structured_logger_developer_compatibility(capsys):
    dev_logger = StructuredLogger("developer_test")
    dev_logger.info("Task completed", context={"password": "secret", "user_id": 42})

    captured = capsys.readouterr()
    assert captured.out, "Expected stdout log print"
    entry = json.loads(captured.out.strip().splitlines()[-1])
    assert entry["subsystem"] == "developer_test"
    assert entry["level"] == "INFO"
    assert entry["context"]["password"] == "[REDACTED]"
    assert entry["context"]["user_id"] == 42


def test_structured_logging_middleware():
    app = FastAPI()
    app.add_middleware(StructuredLoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/items/{item_id}")
    def get_item(item_id: int):
        return {"item_id": item_id}

    @app.get("/fail")
    def fail():
        raise HTTPException(status_code=400, detail="Invalid request")

    client = TestClient(app, raise_server_exceptions=False)

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    formatter = OrchestraJsonFormatter()
    handler.setFormatter(formatter)
    access_logger = logging.getLogger("orchestra.access")
    access_logger.handlers = [handler]
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = False

    # Test success
    resp = client.get("/items/42", headers={"X-Request-ID": "req_access_001"})
    assert resp.status_code == 200

    # Test error
    resp_fail = client.get("/fail")
    assert resp_fail.status_code == 400

    logs = [json.loads(line) for line in stream.getvalue().strip().splitlines() if line]
    assert len(logs) == 2

    # Validate first log
    assert logs[0]["request_id"] == "req_access_001"
    assert logs[0]["method"] == "GET"
    assert logs[0]["status_code"] == 200
    assert logs[0]["duration_ms"] >= 0
    assert "password" not in logs[0]

    # Validate second log
    assert logs[1]["status_code"] == 400
    assert logs[1]["error_category"] == "authentication_error" or logs[1]["status_code"] == 400
