from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Server-side CSRF defense for cookie-authenticated mutating requests.

    Rules:
    1. Safe methods (GET, HEAD, OPTIONS) bypass CSRF checks.
    2. Bearer-authenticated requests (Authorization: Bearer ...) bypass CSRF checks (API clients).
    3. Authentication routes (/auth/login, /auth/register, /auth/refresh, /auth/logout) bypass CSRF checks.
    4. Mutating requests (POST, PUT, PATCH, DELETE) that are cookie-authenticated
       (contain 'access_token' or 'refresh_token' cookies and NO Bearer Authorization header)
       MUST contain 'X-Orchestra-Request: true'.
       If the header is missing or not 'true', reject with HTTP 403 Forbidden.
    """

    EXEMPT_PATHS = {
        "/auth/login",
        "/auth/register",
        "/auth/refresh",
        "/auth/logout",
    }

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in self.SAFE_METHODS:
            return await call_next(request)

        path = request.url.path.rstrip("/")
        if path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Check Bearer authorization header precedence
        auth_header = request.headers.get("authorization", "")
        if auth_header.strip().lower().startswith("bearer "):
            return await call_next(request)

        # Check if cookie-authenticated
        has_auth_cookie = bool(
            request.cookies.get("access_token") or request.cookies.get("refresh_token")
        )
        if has_auth_cookie:
            csrf_header = request.headers.get("x-orchestra-request", "").strip().lower()
            if csrf_header != "true":
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "CSRF protection header 'X-Orchestra-Request: true' missing or invalid."},
                )

        return await call_next(request)
