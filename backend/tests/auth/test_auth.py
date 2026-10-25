"""
Authentication lifecycle, token handling, cookie management, and header precedence tests.
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

from app.auth.jwt import ALGORITHM, create_access_token, create_refresh_token
from app.core.config import settings
from app.models.user import User, UserRole


def test_register_success(client: TestClient, db_session: Session):
    """Verify public registration creates user with 201 Created and default 'member' role."""
    payload = {
        "email": "newuser@orchestra.ai",
        "password": "ValidPassword123!",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@orchestra.ai"
    assert data["role"] == "member"
    assert "id" in data
    assert "password" not in data
    assert "password_hash" not in data

    # Verify database persistence
    user = db_session.query(User).filter(User.email == "newuser@orchestra.ai").first()
    assert user is not None
    assert user.role == UserRole.MEMBER.value
    assert user.password_hash.startswith("$2b$")


def test_register_duplicate_email(client: TestClient, member_user: User):
    """Verify registration rejects duplicate email with 409 Conflict."""
    payload = {
        "email": member_user.email,
        "password": "AnotherPassword123!",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"


def test_register_stores_hash_never_plaintext(client: TestClient, db_session: Session):
    """Verify that plaintext password is never stored or exposed."""
    raw_password = "SecretNeverPlaintext999!"
    payload = {
        "email": "hashcheck@orchestra.ai",
        "password": raw_password,
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201

    user = db_session.query(User).filter(User.email == "hashcheck@orchestra.ai").first()
    assert user.password_hash != raw_password
    assert raw_password not in user.password_hash


def test_login_success_bearer_and_cookies(client: TestClient, member_user: User):
    """Verify valid credentials return access & refresh tokens in body and set HttpOnly cookies."""
    payload = {
        "email": member_user.email,
        "password": "MemberSecret123!",
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

    # Verify cookies
    cookies = response.cookies
    assert "access_token" in cookies
    assert "refresh_token" in cookies
    assert response.headers.get("set-cookie") is not None
    assert "HttpOnly" in response.headers.get("set-cookie")


def test_login_form_data_support(client: TestClient, member_user: User):
    """Verify login works with standard OAuth2 form-encoded data."""
    form_data = {
        "username": member_user.email,
        "password": "MemberSecret123!",
    }
    response = client.post("/auth/login", data=form_data)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_password(client: TestClient, member_user: User):
    """Verify invalid password returns generic 401 Unauthorized."""
    payload = {
        "email": member_user.email,
        "password": "WrongPasswordAttempt",
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_nonexistent_user(client: TestClient):
    """Verify nonexistent email returns identical generic 401 Unauthorized (anti-enumeration)."""
    payload = {
        "email": "doesnotexist@orchestra.ai",
        "password": "AnyPassword123!",
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_get_me_bearer_auth(client: TestClient, member_user: User):
    """Verify valid Bearer access token retrieves user profile with role."""
    token = create_access_token(member_user.id, role=member_user.role)
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == member_user.id
    assert data["email"] == member_user.email
    assert data["role"] == "member"


def test_get_me_cookie_auth(client: TestClient, member_user: User):
    """Verify valid access_token cookie retrieves user profile when Bearer header is absent."""
    token = create_access_token(member_user.id, role=member_user.role)
    client.cookies.set("access_token", token)
    response = client.get("/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == member_user.id
    assert data["email"] == member_user.email


def test_get_me_missing_auth(client: TestClient):
    """Verify unauthenticated request to /auth/me returns 401."""
    client.cookies.clear()
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_get_me_malformed_bearer(client: TestClient):
    """Verify malformed Bearer header returns 401."""
    response = client.get("/auth/me", headers={"Authorization": "Bearer malformed.jwt.token"})
    assert response.status_code == 401


def test_get_me_expired_bearer(client: TestClient, member_user: User):
    """Verify expired Bearer token returns 401."""
    token = create_access_token(member_user.id, role=member_user.role, expires_minutes=-10)
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_header_precedence_invalid_bearer_does_not_fall_back_to_cookie(
    client: TestClient, member_user: User
):
    """
    CRITICAL SECURITY CHECK:
    When an Authorization header is provided with an INVALID token,
    authentication MUST return 401 immediately and NEVER fall back to a valid cookie!
    """
    valid_cookie_token = create_access_token(member_user.id, role=member_user.role)
    client.cookies.set("access_token", valid_cookie_token)

    # Provide an invalid Bearer token
    response = client.get("/auth/me", headers={"Authorization": "Bearer invalid_bearer_token"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


def test_jwt_refresh_token_rejected_for_resource(client: TestClient, member_user: User):
    """Verify that a refresh token CANNOT be used as an access token to access /auth/me."""
    refresh_token = create_refresh_token(member_user.id)
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {refresh_token}"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


def test_jwt_access_token_rejected_as_refresh(client: TestClient, member_user: User):
    """Verify that an access token CANNOT be used at /auth/refresh."""
    access_token = create_access_token(member_user.id, role=member_user.role)
    response = client.post("/auth/refresh", json={"refresh_token": access_token})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired refresh token"


def test_token_refresh_from_cookie(client: TestClient, member_user: User):
    """Verify refresh token in cookie successfully generates new access token."""
    refresh_token = create_refresh_token(member_user.id)
    client.cookies.set("refresh_token", refresh_token)

    response = client.post("/auth/refresh")
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "access_token" in response.cookies


def test_token_refresh_from_payload(client: TestClient, member_user: User):
    """Verify refresh token in JSON payload successfully generates new access token."""
    client.cookies.clear()
    refresh_token = create_refresh_token(member_user.id)

    response = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_token_refresh_expired(client: TestClient, member_user: User):
    """Verify expired refresh token returns 401."""
    expired_refresh = create_refresh_token(member_user.id, expires_days=-1)
    response = client.post("/auth/refresh", json={"refresh_token": expired_refresh})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired refresh token"


def test_logout_clears_cookies(client: TestClient, member_user: User):
    """Verify /auth/logout sets cookie deletion headers for session logout."""
    # Login first
    login_resp = client.post(
        "/auth/login",
        json={"email": member_user.email, "password": "MemberSecret123!"},
    )
    assert login_resp.status_code == 200

    # Logout
    logout_resp = client.post("/auth/logout")
    assert logout_resp.status_code == 200
    assert logout_resp.json()["message"] == "Logged out successfully"

    # Verify cookies deleted/cleared in response headers
    set_cookie_header = logout_resp.headers.get("set-cookie", "")
    assert 'access_token=""' in set_cookie_header or 'access_token=;' in set_cookie_header
    assert 'refresh_token=""' in set_cookie_header or 'refresh_token=;' in set_cookie_header
