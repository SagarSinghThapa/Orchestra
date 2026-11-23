"""
Authentication lifecycle, token handling, cookie management, and header precedence tests.
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

from app.auth.jwt import ALGORITHM, create_access_token, create_refresh_token
from app.auth.password import hash_password
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


def test_register_normalizes_email_to_lowercase(client: TestClient, db_session: Session):
    """Verify registration normalizes mixed-case email to lowercase."""
    raw_email = "  MixedCase_User@Orchestra.AI  "
    payload = {
        "email": raw_email,
        "password": "ValidPassword123!",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "mixedcase_user@orchestra.ai"

    # Verify DB storage is lowercase
    user = db_session.query(User).filter(User.email == "mixedcase_user@orchestra.ai").first()
    assert user is not None


def test_login_case_insensitive_matching(client: TestClient, db_session: Session):
    """Verify login succeeds when email has different casing than registered."""
    # Register lowercase user
    payload = {
        "email": "casetester@orchestra.ai",
        "password": "ValidPassword123!",
    }
    reg_resp = client.post("/auth/register", json=payload)
    assert reg_resp.status_code == 201

    # Login with mixed case
    login_resp = client.post(
        "/auth/login",
        json={"email": "CaseTester@Orchestra.AI", "password": "ValidPassword123!"},
    )
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()


def test_login_tolerates_surrounding_whitespace(client: TestClient, db_session: Session):
    """Verify login tolerates leading/trailing whitespace in email."""
    payload = {
        "email": "whitespacetest@orchestra.ai",
        "password": "ValidPassword123!",
    }
    reg_resp = client.post("/auth/register", json=payload)
    assert reg_resp.status_code == 201

    # Login with surrounding spaces
    login_resp = client.post(
        "/auth/login",
        json={"email": "  whitespacetest@orchestra.ai  \t", "password": "ValidPassword123!"},
    )
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()


def test_register_duplicate_rejection_case_insensitive(client: TestClient, db_session: Session):
    """Verify registration rejects duplicate email regardless of casing."""
    payload = {
        "email": "original@orchestra.ai",
        "password": "ValidPassword123!",
    }
    reg_resp = client.post("/auth/register", json=payload)
    assert reg_resp.status_code == 201

    # Attempt to register with uppercase variant
    dup_payload = {
        "email": "ORIGINAL@ORCHESTRA.AI",
        "password": "AnotherPassword123!",
    }
    dup_resp = client.post("/auth/register", json=dup_payload)
    assert dup_resp.status_code == 409
    assert dup_resp.json()["detail"] == "Email already registered"


def test_login_collision_fails_closed_without_information_disclosure(
    client: TestClient, db_session: Session
):
    """
    Verify collision safety:
    1. If exact match exists, legacy exact-match succeeds.
    2. If case-insensitive match returns multiple accounts and NO exact match exists,
       it FAILS CLOSED (never selects oldest, never mutates) and returns generic 401
       without leaking candidate IDs or email addresses.
    """
    # Create two collision accounts directly in DB with different casing
    user_lower = User(
        email="collision_target@orchestra.ai",
        password_hash=hash_password("LowerPass123!"),
        role=UserRole.MEMBER.value,
    )
    user_upper = User(
        email="COLLISION_TARGET@ORCHESTRA.AI",
        password_hash=hash_password("UpperPass123!"),
        role=UserRole.MEMBER.value,
    )
    db_session.add(user_lower)
    db_session.add(user_upper)
    db_session.commit()
    db_session.refresh(user_lower)
    db_session.refresh(user_upper)

    lower_id = user_lower.id
    upper_id = user_upper.id

    # 1. Exact match for lower succeeds
    res_lower = client.post(
        "/auth/login",
        json={"email": "collision_target@orchestra.ai", "password": "LowerPass123!"},
    )
    assert res_lower.status_code == 200

    # 2. Exact match for upper succeeds
    res_upper = client.post(
        "/auth/login",
        json={"email": "COLLISION_TARGET@ORCHESTRA.AI", "password": "UpperPass123!"},
    )
    assert res_upper.status_code == 200

    # 3. Ambiguous lookup (neither exact match): e.g. "Collision_Target@Orchestra.AI"
    # Matches both case-insensitively -> MUST FAIL CLOSED
    res_ambiguous = client.post(
        "/auth/login",
        json={"email": "Collision_Target@Orchestra.AI", "password": "LowerPass123!"},
    )
    assert res_ambiguous.status_code == 401
    err_body = res_ambiguous.json()
    assert err_body["detail"] == "Invalid email or password"

    # Verify zero information disclosure: no candidate IDs, no counts, no emails leaked
    response_text = res_ambiguous.text
    assert str(lower_id) not in response_text
    assert str(upper_id) not in response_text
    assert "collision_target" not in response_text
    assert "candidates" not in response_text

    # Verify zero mutation: both DB records still exist and are untouched
    check_lower = db_session.query(User).filter(User.id == lower_id).first()
    check_upper = db_session.query(User).filter(User.id == upper_id).first()
    assert check_lower is not None
    assert check_upper is not None
    assert check_lower.email == "collision_target@orchestra.ai"
    assert check_upper.email == "COLLISION_TARGET@ORCHESTRA.AI"


def test_logout_revokes_access_token_replay_rejected(client: TestClient, member_user: User):
    """Verify that logged-out access tokens cannot be replayed (server-side invalidation)."""
    login_res = client.post(
        "/auth/login",
        json={"email": member_user.email, "password": "MemberSecret123!"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # Access token is valid before logout
    me_res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200

    # Perform logout
    logout_res = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_res.status_code == 200

    # Token replay must be rejected with 401
    me_after_res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_after_res.status_code == 401
    assert "revoked" in me_after_res.json()["detail"].lower()


def test_logout_revokes_refresh_token(client: TestClient, member_user: User):
    """Verify that logged-out refresh tokens cannot be used to generate new access tokens."""
    login_res = client.post(
        "/auth/login",
        json={"email": member_user.email, "password": "MemberSecret123!"},
    )
    assert login_res.status_code == 200
    refresh_token = login_res.json()["refresh_token"]

    # Logout revoking refresh token
    client.post("/auth/logout", cookies={"refresh_token": refresh_token})

    # Attempt to refresh with revoked refresh token
    refresh_res = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_res.status_code == 401
    assert "revoked" in refresh_res.json()["detail"].lower()


def test_csrf_rejects_untrusted_origin_on_cookie_mutation(client: TestClient, member_user: User):
    """Verify that cookie-authenticated state-changing requests reject untrusted origins."""
    login_res = client.post(
        "/auth/login",
        json={"email": member_user.email, "password": "MemberSecret123!"},
    )
    assert login_res.status_code == 200
    access_cookie = login_res.cookies.get("access_token")

    # Mutating request with untrusted origin
    mutation_res = client.post(
        "/sessions",
        cookies={"access_token": access_cookie},
        headers={"Origin": "https://evil-untrusted-site.com"},
        json={"title": "Unauthorized Session", "query": "Test"},
    )
    assert mutation_res.status_code == 403
    assert "CSRF verification failed" in mutation_res.json()["detail"]


def test_csrf_rejects_missing_origin_and_referer(client: TestClient, member_user: User):
    """Verify that cookie-authenticated mutations reject missing origin/referer."""
    login_res = client.post(
        "/auth/login",
        json={"email": member_user.email, "password": "MemberSecret123!"},
    )
    assert login_res.status_code == 200
    access_cookie = login_res.cookies.get("access_token")

    mutation_res = client.post(
        "/sessions",
        cookies={"access_token": access_cookie},
        # No Origin or Referer header supplied
        json={"title": "Missing Origin Session", "query": "Test"},
    )
    assert mutation_res.status_code == 403
    assert "CSRF verification failed" in mutation_res.json()["detail"]


def test_csrf_accepts_trusted_origin_and_session_token(client: TestClient, member_user: User):
    """Verify that cookie-authenticated mutations succeed with trusted origin and session CSRF token."""
    login_res = client.post(
        "/auth/login",
        json={"email": member_user.email, "password": "MemberSecret123!"},
    )
    assert login_res.status_code == 200
    access_cookie = login_res.cookies.get("access_token")
    csrf_cookie = login_res.cookies.get("csrf_token")
    assert csrf_cookie is not None

    mutation_res = client.post(
        "/sessions",
        cookies={"access_token": access_cookie, "csrf_token": csrf_cookie},
        headers={
            "Origin": "http://localhost:3000",
            "X-CSRF-Token": csrf_cookie,
        },
        json={"title": "Legitimate Session", "query": "How to optimize queries?"},
    )
    # Passed CSRF check (fails further downstream on missing project_id, but NOT 403 CSRF rejection)
    assert mutation_res.status_code != 403


def test_production_config_guard_enforces_secure_cookies():
    """Verify production startup validation rejects insecure cookie override."""
    from app.core.config import Settings

    # Setting environment=production with cookie_secure=False must raise RuntimeError
    s = Settings(
        environment="production",
        database_url="postgresql+psycopg://user:pass@localhost:5432/db",
        jwt_secret="prod-secret-32-chars-long-security-key!",
        cookie_secure=False,
    )
    with pytest.raises(RuntimeError, match="COOKIE_SECURE cannot be false in production"):
        s.validate_runtime_requirements()


def test_logout_deletes_both_auth_cookies_with_matching_attributes(client: TestClient, member_user: User):
    """Verify logout emits Set-Cookie clearing access, refresh, and csrf cookies with Path=/."""
    res = client.post("/auth/logout")
    assert res.status_code == 200

    set_cookie_headers = [v for k, v in res.headers.raw if k.lower() == b"set-cookie"]
    cookie_str = " ".join([h.decode() for h in set_cookie_headers])

    assert "access_token=" in cookie_str
    assert "refresh_token=" in cookie_str
    assert "csrf_token=" in cookie_str
    assert "Path=/" in cookie_str


def test_revocation_store_fails_securely_in_production_when_redis_unavailable(
    client: TestClient, member_user: User, monkeypatch
):
    """Verify that in production mode, if Redis is unavailable, token revocation check fails closed."""
    login_res = client.post(
        "/auth/login",
        json={"email": member_user.email, "password": "MemberSecret123!"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # Simulate production environment without Redis
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr("app.core.token_blocklist.get_redis_client", lambda: None)

    # Calling an authenticated route must fail closed with 503 Service Unavailable
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 503
    assert "unavailable" in res.json()["detail"].lower()


def test_legacy_orchestra_header_cannot_bypass_csrf_in_production(
    client: TestClient, member_user: User, monkeypatch
):
    """
    Verify that in production mode, the legacy X-Orchestra-Request header cannot
    independently bypass CSRF protection without a valid session-bound CSRF token.
    """
    login_res = client.post(
        "/auth/login",
        json={"email": member_user.email, "password": "MemberSecret123!"},
    )
    assert login_res.status_code == 200
    access_cookie = login_res.cookies.get("access_token")

    # Clear session csrf_token cookie to verify header alone cannot bypass
    client.cookies.delete("csrf_token")

    monkeypatch.setattr(settings, "environment", "production")

    # Present trusted origin and legacy header, but omit session CSRF token
    res = client.post(
        "/sessions",
        cookies={"access_token": access_cookie},
        headers={
            "Origin": "http://localhost:3000",
            "X-Orchestra-Request": "true",
        },
        json={"title": "Test Session", "query": "Test"},
    )
    assert res.status_code == 403
    assert "session csrf token" in res.json()["detail"].lower()




