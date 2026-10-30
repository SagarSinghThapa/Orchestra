"""
Tests for CORS and CSRF protection middleware in Orchestra.
"""
import pytest
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.core.config import settings
from app.models.user import User
from app.models.project import Project


@pytest.fixture(autouse=True)
def test_env():
    old_secret = settings.jwt_secret
    old_db = settings.database_url
    settings.jwt_secret = "test-secret-key-32-chars-minimum-length!!"
    settings.database_url = "sqlite:///:memory:"
    yield
    settings.jwt_secret = old_secret
    settings.database_url = old_db


def test_cors_preflight_trusted_origin(client: TestClient):
    """Verify OPTIONS preflight request from trusted origin receives CORS headers."""
    response = client.options(
        "/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Orchestra-Request,Content-Type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert "x-orchestra-request" in response.headers.get("access-control-allow-headers", "").lower()


def test_cors_preflight_untrusted_origin(client: TestClient):
    """Verify OPTIONS preflight request from untrusted origin does NOT receive allow-origin."""
    response = client.options(
        "/auth/login",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Orchestra-Request,Content-Type",
        },
    )
    assert response.headers.get("access-control-allow-origin") is None


def test_csrf_cookie_post_missing_header_rejected(client: TestClient, test_user: User):
    """Verify cookie-authenticated mutating request WITHOUT X-Orchestra-Request is rejected with 403."""
    token = create_access_token(test_user.id, role=test_user.role)
    client.cookies.set("access_token", token)

    response = client.post("/projects", json={"name": "Attacker Project"})
    assert response.status_code == 403
    assert "CSRF protection header" in response.json()["detail"]


def test_csrf_cookie_post_invalid_header_rejected(client: TestClient, test_user: User):
    """Verify cookie-authenticated mutating request with invalid CSRF header is rejected with 403."""
    token = create_access_token(test_user.id, role=test_user.role)
    client.cookies.set("access_token", token)

    response = client.post(
        "/projects",
        json={"name": "Attacker Project"},
        headers={"X-Orchestra-Request": "false"},
    )
    assert response.status_code == 403
    assert "CSRF protection header" in response.json()["detail"]


def test_csrf_cookie_post_with_header_succeeds(client: TestClient, test_user: User):
    """Verify cookie-authenticated mutating request WITH X-Orchestra-Request: true succeeds."""
    token = create_access_token(test_user.id, role=test_user.role)
    client.cookies.set("access_token", token)

    response = client.post(
        "/projects",
        json={"name": "Legitimate Project"},
        headers={"X-Orchestra-Request": "true"},
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Legitimate Project"


def test_csrf_cookie_delete_with_header_succeeds(
    client: TestClient, test_user: User, test_project: Project
):
    """Verify cookie-authenticated DELETE request WITH X-Orchestra-Request: true succeeds."""
    token = create_access_token(test_user.id, role=test_user.role)
    client.cookies.set("access_token", token)

    # Without header -> 403
    resp_blocked = client.delete(f"/projects/{test_project.id}")
    assert resp_blocked.status_code == 403

    # With header -> 204
    resp_ok = client.delete(
        f"/projects/{test_project.id}",
        headers={"X-Orchestra-Request": "true"},
    )
    assert resp_ok.status_code == 204


def test_csrf_bearer_client_exempt(client: TestClient, test_user: User):
    """Verify programmatic API clients using Authorization: Bearer are exempt from CSRF header."""
    token = create_access_token(test_user.id, role=test_user.role)
    client.cookies.clear()

    response = client.post(
        "/projects",
        json={"name": "Bearer Project"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Bearer Project"


def test_csrf_safe_methods_exempt(client: TestClient, test_user: User):
    """Verify GET safe methods with cookies bypass CSRF check."""
    token = create_access_token(test_user.id, role=test_user.role)
    client.cookies.set("access_token", token)

    response = client.get("/projects")
    assert response.status_code == 200
