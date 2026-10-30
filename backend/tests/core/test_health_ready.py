import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.core.config import settings


def test_liveness_health_endpoint():
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy"}


def test_readiness_healthy(monkeypatch):
    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "rate_limit_backend", "memory")

    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    with patch("app.main.engine", mock_engine), patch("app.main.get_redis_health", return_value={"status": "healthy"}), patch("qdrant_client.AsyncQdrantClient.get_collections", return_value=[]):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["dependencies"]["database"] == "healthy"
        assert data["dependencies"]["redis"] == "healthy"
        assert data["dependencies"]["qdrant"] == "healthy"


def test_readiness_fails_when_db_down(monkeypatch):
    monkeypatch.setattr(settings, "environment", "test")

    with patch("app.main.engine", None):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "not_ready"
        assert data["dependencies"]["database"] == "unconfigured"


def test_cors_preflight_and_header_exposure():
    client = TestClient(app, raise_server_exceptions=False)

    # 1. OPTIONS preflight
    resp_options = client.options(
        "/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, X-Orchestra-Request, Authorization, X-Request-ID",
        },
    )
    assert resp_options.status_code == 200
    assert resp_options.headers.get("access-control-allow-origin") == "http://localhost:3000"

    # 2. Actual GET/POST response carries Access-Control-Expose-Headers
    resp_get = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert resp_get.status_code == 200
    assert resp_get.headers.get("access-control-allow-origin") == "http://localhost:3000"
    expose_headers = resp_get.headers.get("access-control-expose-headers", "").lower()
    assert "x-request-id" in expose_headers
    assert "retry-after" in expose_headers


def test_cors_headers_on_429(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "rate_limit_backend", "memory")

    client = TestClient(app, raise_server_exceptions=False)

    # Exhaust /auth/login limit (5 requests)
    for _ in range(5):
        client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "wrong"},
            headers={"Origin": "http://localhost:3000"},
        )

    resp_429 = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "wrong"},
        headers={"Origin": "http://localhost:3000"},
    )
    assert resp_429.status_code == 429
    assert resp_429.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "X-Request-ID" in resp_429.headers
    assert "Retry-After" in resp_429.headers
