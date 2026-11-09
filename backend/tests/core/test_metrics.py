import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.metrics import (
    get_metrics_output,
    get_status_class,
    metrics_registry,
    record_http_request,
    record_llm_call,
    record_rate_limit_rejection,
)
from app.core.middleware import MetricsMiddleware, RequestIDMiddleware


def test_get_status_class():
    assert get_status_class(200) == "2xx"
    assert get_status_class(201) == "2xx"
    assert get_status_class(304) == "3xx"
    assert get_status_class(400) == "4xx"
    assert get_status_class(404) == "4xx"
    assert get_status_class(429) == "4xx"
    assert get_status_class(500) == "5xx"
    assert get_status_class(503) == "5xx"
    assert get_status_class(100) == "other"


def test_metric_recorders_and_output():
    # Record events
    record_http_request("POST", "/projects/{project_id}/research", 200, 0.42)
    record_http_request("POST", "/projects/{project_id}/research", 429, 0.05)
    record_rate_limit_rejection("RESEARCH")
    record_llm_call("openai_compatible", "success", 1.25)
    record_llm_call("openai_compatible", "error", 0.3)

    output = get_metrics_output().decode("utf-8")
    assert "orchestra_http_requests_total" in output
    assert 'route="/projects/{project_id}/research"' in output
    assert 'status_class="2xx"' in output
    assert "orchestra_rate_limit_rejections_total" in output
    assert 'route_class="RESEARCH"' in output
    assert "orchestra_llm_calls_total" in output
    assert 'provider="openai_compatible"' in output


def test_metrics_endpoint_disabled_by_default():
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    # Default is metrics_enabled = False
    assert settings.metrics_enabled is False
    resp = client.get("/metrics")
    assert resp.status_code == 404
    assert "disabled" in resp.json()["detail"].lower()


def test_metrics_endpoint_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "metrics_enabled", True)
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "orchestra_http_requests_total" in resp.text


def test_metrics_cardinality_guard():
    # Inspect all registered metric label sets
    prohibited_substrings = ["user_id", "project_id", "session_id", "document_id", "email", "prompt"]

    for metric in metrics_registry.collect():
        for sample in metric.samples:
            for label_name in sample.labels.keys():
                for prohibited in prohibited_substrings:
                    assert prohibited != label_name, f"Prohibited cardinality label '{label_name}' found in {metric.name}"
