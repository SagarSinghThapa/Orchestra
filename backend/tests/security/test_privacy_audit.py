import io
import json
import logging
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.logging import OrchestraJsonFormatter, scrub_secrets
from app.core.telemetry import captured_spans, trace_span
from app.main import app


def test_synthetic_secret_redaction_audit():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(OrchestraJsonFormatter())
    audit_logger = logging.getLogger("audit.privacy")
    audit_logger.handlers = [handler]
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False

    synthetic_jwt = "eyJhGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI5OTk5OSJ9.synthetic_jwt_token_xyz"
    synthetic_openai_key = "sk-synthetic_openai_key_abcdef123456"
    synthetic_github_token = "ghp_synthetic_github_token_abcdef12"
    synthetic_aws_key = "AKIA9876543210ZYXWVU"

    audit_logger.info(f"Log event with JWT={synthetic_jwt} and Key={synthetic_openai_key}")
    audit_logger.info(f"Log event with GitHub={synthetic_github_token} and AWS={synthetic_aws_key}")
    audit_logger.info("Log event with dict", extra={"token": synthetic_jwt, "api_key": synthetic_openai_key})

    log_output = stream.getvalue()

    # Raw secrets must NOT appear
    assert synthetic_jwt not in log_output
    assert synthetic_openai_key not in log_output
    assert synthetic_github_token not in log_output
    assert synthetic_aws_key not in log_output

    # Redaction placeholders must appear
    assert "[REDACTED_JWT]" in log_output
    assert "sk-[REDACTED_KEY]" in log_output
    assert "gh_[REDACTED_TOKEN]" in log_output
    assert "AKIA[REDACTED_AWS]" in log_output


def test_inviolable_never_log_invariant(monkeypatch):
    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "rate_limit_backend", "memory")

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(OrchestraJsonFormatter())
    access_logger = logging.getLogger("orchestra.access")
    access_logger.handlers = [handler]
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = False

    synthetic_prompt = "SYNTHETIC_PROMPT_QUANTUM_COMPUTING_EXPLANATION_XYZ"
    synthetic_doc_content = "SYNTHETIC_DOCUMENT_CHUNK_CONTENT_EMBEDDING_XYZ"
    synthetic_source_code = "def synthetic_secret_function_xyz(): return 42"
    synthetic_diff = "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-old\n+new_synthetic_diff"

    client = TestClient(app, raise_server_exceptions=False)

    # Post requests containing synthetic content
    client.post("/auth/login", json={"email": "test@example.com", "password": synthetic_prompt})
    client.get("/health?q=" + synthetic_doc_content)

    log_output = stream.getvalue()

    # Inviolable NEVER LOG verification:
    assert synthetic_prompt not in log_output, "User prompt/password found in access log!"
    assert synthetic_doc_content not in log_output, "Document content/query found in access log!"
    assert synthetic_source_code not in log_output, "Source code found in access log!"
    assert synthetic_diff not in log_output, "Diff found in access log!"


def test_telemetry_span_privacy_audit(monkeypatch):
    monkeypatch.setattr(settings, "otel_enabled", True)
    captured_spans.clear()

    synthetic_prompt = "SECRET_PROMPT_NEVER_ENTER_TRACE_SPANS"
    synthetic_doc = "SECRET_DOCUMENT_TEXT_NEVER_ENTER_TRACE_SPANS"
    synthetic_code = "SECRET_SOURCE_CODE_NEVER_ENTER_TRACE_SPANS"

    with trace_span(
        "orchestrator_turn",
        {
            "route": "/projects/{project_id}/orchestrate",
            "provider": "openai_compatible",
            "prompt": synthetic_prompt,
            "document": synthetic_doc,
            "code": synthetic_code,
            "tokens_prompt": 100,
        },
    ):
        pass

    assert len(captured_spans) == 1
    span_str = str(captured_spans[0])

    assert synthetic_prompt not in span_str
    assert synthetic_doc not in span_str
    assert synthetic_code not in span_str
    assert captured_spans[0]["attributes"]["tokens_prompt"] == 100
