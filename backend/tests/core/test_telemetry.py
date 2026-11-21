import os
import pytest

from app.core.config import settings
from app.core.context import reset_request_id, set_request_id
from app.core.telemetry import (
    captured_spans,
    configure_langsmith_tracing,
    sanitize_span_attributes,
    trace_span,
)


def test_sanitize_span_attributes():
    raw_attrs = {
        "operation": "test_op",
        "route": "/projects/{project_id}/developer",
        "provider": "openai_compatible",
        "prompt": "Here is my secret user prompt",
        "message": "User query",
        "code": "def secret_code(): pass",
        "jwt": "eyJhGciOiJIUzI1NiIsInR5c...",
        "tokens_prompt": 150,
        "tokens_completion": 45,
    }

    sanitized = sanitize_span_attributes(raw_attrs)
    assert "operation" in sanitized
    assert "route" in sanitized
    assert "provider" in sanitized
    assert "tokens_prompt" in sanitized
    assert "tokens_completion" in sanitized

    # Assert strictly stripped
    assert "prompt" not in sanitized
    assert "message" not in sanitized
    assert "code" not in sanitized
    assert "jwt" not in sanitized


def test_trace_span_noop_when_disabled():
    captured_spans.clear()
    assert settings.otel_enabled is False

    with trace_span("http_request", {"route": "/test", "prompt": "ignored"}):
        pass

    assert len(captured_spans) == 0


def test_trace_span_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "otel_enabled", True)
    captured_spans.clear()

    token = set_request_id("req_trace_test_42")
    try:
        with trace_span(
            "llm_generate",
            {
                "provider": "openai_compatible",
                "tokens_prompt": 120,
                "tokens_completion": 80,
                "prompt": "SECRET_PROMPT_THAT_MUST_BE_STRIPPED",
            },
        ) as span:
            assert span["operation"] == "llm_generate"
    finally:
        reset_request_id(token)

    assert len(captured_spans) == 1
    recorded = captured_spans[0]
    assert recorded["operation"] == "llm_generate"
    assert recorded["status"] == "ok"
    assert recorded["duration_ms"] >= 0
    assert recorded["attributes"]["provider"] == "openai_compatible"
    assert recorded["attributes"]["tokens_prompt"] == 120
    assert recorded["attributes"]["request_id"] == "req_trace_test_42"

    # Privacy verification
    assert "prompt" not in recorded["attributes"]
    assert "SECRET_PROMPT" not in str(recorded)


def test_configure_langsmith_tracing_disabled_by_default(monkeypatch):
    monkeypatch.setattr(settings, "langsmith_tracing", False)
    # Ensure clean env state
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")

    res = configure_langsmith_tracing()
    assert res is False
    assert os.environ.get("LANGCHAIN_TRACING_V2") == "false"
    assert os.environ.get("LANGSMITH_TRACING") == "false"


def test_configure_langsmith_tracing_opt_in_with_privacy_masking(monkeypatch):
    monkeypatch.setattr(settings, "langsmith_tracing", True)

    res = configure_langsmith_tracing()
    assert res is True
    assert os.environ.get("LANGCHAIN_TRACING_V2") == "true"
    assert os.environ.get("LANGSMITH_TRACING") == "true"
    # Inviolable privacy safeguards: raw inputs and outputs are masked
    assert os.environ.get("LANGCHAIN_HIDE_INPUTS") == "true"
    assert os.environ.get("LANGCHAIN_HIDE_OUTPUTS") == "true"
