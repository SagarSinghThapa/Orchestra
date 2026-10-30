import pytest
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.core.config import settings
from app.main import app


@pytest.fixture(autouse=True)
def configure_test_environment(monkeypatch):
    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "rate_limit_backend", "memory")
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "jwt_secret", "test_jwt_secret_key_hardening_12345")


def test_rate_limit_quota_exhaustion_on_auth():
    from unittest.mock import MagicMock
    from app.database.connection import get_db

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        client = TestClient(app, raise_server_exceptions=False)

        for i in range(5):
            resp = client.post(
                "/auth/login",
                json={"email": f"test{i}@example.com", "password": "wrongpassword"},
            )
            assert resp.status_code == 401 or resp.status_code == 200

        # 6th request triggers 429
        resp_429 = client.post(
            "/auth/login",
            json={"email": "test6@example.com", "password": "wrongpassword"},
        )
        assert resp_429.status_code == 429
        assert "Retry-After" in resp_429.headers
        assert "X-Request-ID" in resp_429.headers
        assert resp_429.json()["error_category"] == "rate_limited"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_csrf_cookie_mutating_enforcement():
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set("access_token", "fake_access_token")

    # Mutating POST with cookie and NO X-Orchestra-Request header -> 403 Forbidden
    resp = client.post("/projects", json={"name": "CSRF Attack Project"})
    assert resp.status_code == 403
    assert "CSRF" in resp.json()["detail"]


def test_bearer_client_csrf_exemption_but_rate_limited():
    client = TestClient(app, raise_server_exceptions=False)
    token = create_access_token(42, role="member")

    # Bearer client does NOT need X-Orchestra-Request header
    # It passes CSRF checks (reaches endpoint or auth layer)
    resp = client.get("/projects", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code != 403 or "CSRF" not in str(resp.json().get("detail", ""))


def test_request_id_correlation_end_to_end():
    client = TestClient(app, raise_server_exceptions=False)
    custom_id = "trace-e2e-correlation-98765"

    resp = client.get("/health", headers={"X-Request-ID": custom_id})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == custom_id
