import hmac
import hashlib
import time
import secrets
from urllib.parse import urlparse
from typing import Optional, Union, Set
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.auth.jwt import decode_token


def generate_session_csrf_token(user_id: Union[int, str]) -> str:
    """
    Generates a cryptographically signed, session-bound CSRF token.
    Format: nonce.timestamp.signature
    """
    secret = settings.jwt_secret or "default-insecure-secret"
    nonce = secrets.token_hex(16)
    ts = str(int(time.time()))
    data = f"{user_id}:{nonce}:{ts}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), data, hashlib.sha256).hexdigest()
    return f"{nonce}.{ts}.{sig}"


def validate_session_csrf_token(
    token: Optional[str],
    user_id: Union[int, str],
    max_age_seconds: int = 86400 * 7,
) -> bool:
    """
    Validates that a CSRF token was cryptographically signed by the server's secret,
    is strictly bound to user_id, and has not expired.
    """
    if not token or not settings.jwt_secret:
        return False

    parts = token.split(".")
    if len(parts) != 3:
        return False

    nonce, ts_str, provided_sig = parts
    try:
        ts = int(ts_str)
        if time.time() - ts > max_age_seconds or time.time() < ts - 60:
            return False  # expired or invalid timestamp
    except (ValueError, TypeError):
        return False

    secret = settings.jwt_secret.encode("utf-8")
    data = f"{user_id}:{nonce}:{ts_str}".encode("utf-8")
    expected_sig = hmac.new(secret, data, hashlib.sha256).hexdigest()

    return hmac.compare_digest(provided_sig, expected_sig)


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Server-side CSRF defense for cookie-authenticated mutating requests.

    Rules:
    1. Safe methods (GET, HEAD, OPTIONS) bypass CSRF checks.
    2. Bearer-authenticated requests (Authorization: Bearer ...) bypass CSRF checks (API clients).
    3. Authentication initiation routes (/auth/login, /auth/register) bypass CSRF checks.
    4. Mutating requests (POST, PUT, PATCH, DELETE) that are cookie-authenticated
       (contain 'access_token' or 'refresh_token' cookies and NO Bearer Authorization header):
       a. MUST have a trusted Origin or Referer matching CORS allowed origins or same-origin host.
       b. MUST provide session-bound CSRF token validation matching the authenticated user.
    """

    EXEMPT_PATHS: Set[str] = {
        "/auth/login",
        "/auth/register",
        "/auth/refresh",
        "/auth/logout",
    }

    SAFE_METHODS: Set[str] = {"GET", "HEAD", "OPTIONS"}

    def _get_trusted_origins(self, request: Request) -> set[str]:
        trusted = set()
        raw_origins = settings.cors_allowed_origins
        if isinstance(raw_origins, list):
            for o in raw_origins:
                trusted.add(o.rstrip("/"))
        elif isinstance(raw_origins, str):
            trusted.add(raw_origins.rstrip("/"))

        # Same-origin host
        host = request.headers.get("host")
        if host:
            trusted.add(f"http://{host}".rstrip("/"))
            trusted.add(f"https://{host}".rstrip("/"))

        scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
        base = f"{scheme}://{request.url.netloc}".rstrip("/")
        trusted.add(base)
        return trusted

    def _check_origin(self, request: Request) -> tuple[bool, str]:
        trusted_origins = self._get_trusted_origins(request)

        # 1. Check Origin header
        origin = request.headers.get("origin")
        if origin:
            normalized_origin = origin.rstrip("/")
            if normalized_origin in trusted_origins:
                return (True, "")
            # Allow localhost variants in non-production
            if settings.environment.lower() != "production":
                parsed = urlparse(origin)
                if parsed.hostname in ("localhost", "127.0.0.1"):
                    return (True, "")
            return (False, "untrusted request origin")

        # 2. Check Referer header if Origin is absent
        referer = request.headers.get("referer")
        if referer:
            parsed = urlparse(referer)
            referer_origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
            if referer_origin in trusted_origins:
                return (True, "")
            if settings.environment.lower() != "production":
                if parsed.hostname in ("localhost", "127.0.0.1"):
                    return (True, "")
            return (False, "untrusted request referer")

        # Browser mutating requests with cookies must supply Origin or Referer
        return (False, "missing request origin")

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in self.SAFE_METHODS:
            return await call_next(request)

        path = request.url.path.rstrip("/")
        if path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Check Bearer authorization header precedence (API clients bypass cookie CSRF)
        auth_header = request.headers.get("authorization", "")
        if auth_header.strip().lower().startswith("bearer "):
            return await call_next(request)

        # Check if cookie-authenticated
        access_cookie = request.cookies.get("access_token")
        refresh_cookie = request.cookies.get("refresh_token")
        has_auth_cookie = bool(access_cookie or refresh_cookie)

        if has_auth_cookie:
            custom_header = request.headers.get("x-orchestra-request", "").strip().lower()
            csrf_header = request.headers.get("x-csrf-token")
            csrf_cookie = request.cookies.get("csrf_token")
            is_prod = settings.environment.lower() == "production"

            origin_valid, origin_reason = self._check_origin(request)

            # Untrusted origin/referer is ALWAYS forbidden regardless of environment
            if origin_reason in ("untrusted request origin", "untrusted request referer"):
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "CSRF verification failed: untrusted request origin."},
                )

            # If origin/referer is completely missing:
            if not origin_valid:
                # In non-production, allow test clients if X-Orchestra-Request: true is present
                if not is_prod and custom_header == "true":
                    pass
                else:
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={
                            "detail": (
                                "CSRF verification failed: CSRF protection header 'X-Orchestra-Request: true' "
                                "or trusted request origin missing."
                            )
                        },
                    )

            # Extract user identity to validate session-bound token
            user_id: Optional[str] = None
            if access_cookie:
                try:
                    payload = decode_token(access_cookie, expected_type="access")
                    user_id = str(payload.get("sub", ""))
                except Exception:
                    pass

            # In production, session-bound CSRF token is mandatory
            if is_prod:
                if not user_id:
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": "CSRF verification failed: invalid session."},
                    )
                token_to_verify = csrf_header or csrf_cookie
                if not validate_session_csrf_token(token_to_verify, user_id):
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": "CSRF verification failed: invalid or missing session CSRF token."},
                    )
            else:
                # In non-production (dev/test):
                # Accept session CSRF token OR X-Orchestra-Request: true
                is_valid = False
                if user_id:
                    token_to_verify = csrf_header or csrf_cookie
                    if validate_session_csrf_token(token_to_verify, user_id):
                        is_valid = True
                if not is_valid and custom_header == "true":
                    is_valid = True

                if not is_valid:
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={
                            "detail": (
                                "CSRF verification failed: CSRF protection header 'X-Orchestra-Request: true' "
                                "or session CSRF token missing or invalid."
                            )
                        },
                    )

        return await call_next(request)
