import logging
import re
import time
import uuid
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.context import get_request_id, reset_request_id, set_request_id
from app.core.rate_limit import classify_route, limiter

logger = logging.getLogger("orchestra.access")

REQUEST_ID_REGEX = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Assigns and validates an end-to-end correlation request ID (X-Request-ID).
    Guarantees ContextVar cleanup in a finally block to prevent async context leakage.
    Injects X-Request-ID on all responses (2xx, 3xx, 4xx, 5xx).
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        inbound_id = request.headers.get("x-request-id")
        if inbound_id and REQUEST_ID_REGEX.match(inbound_id):
            request_id = inbound_id
        else:
            request_id = f"req_{uuid.uuid4().hex}"

        request.state.request_id = request_id
        token = set_request_id(request_id)

        try:
            try:
                response = await call_next(request)
            except Exception as exc:
                logger.error(
                    "Unhandled exception in request dispatch",
                    extra={
                        "request_id": request_id,
                        "error_category": "internal_error",
                        "error_type": exc.__class__.__name__,
                    },
                    exc_info=True,
                )
                from starlette.responses import JSONResponse
                response = JSONResponse(
                    status_code=500,
                    content={
                        "detail": "An internal server error occurred.",
                        "request_id": request_id,
                        "error_category": "internal_error",
                    },
                )
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            reset_request_id(token)


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """
    Emits single-line structured JSON access logs upon request completion.
    Strictly observes the NEVER LOG policy: zero logging of request or response bodies,
    passwords, JWTs, prompts, messages, documents, or source code.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()
        error_category: Optional[str] = None
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            if status_code >= 400:
                if status_code == 401:
                    error_category = "authentication_error"
                elif status_code == 403:
                    error_category = "authorization_error"
                elif status_code == 404:
                    error_category = "not_found"
                elif status_code == 422:
                    error_category = "validation_error"
                elif status_code == 429:
                    error_category = "rate_limited"
                elif status_code == 503:
                    error_category = "service_unavailable"
                elif status_code >= 500:
                    error_category = "internal_error"
            return response
        except Exception:
            error_category = "internal_error"
            raise
        finally:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            request_id = getattr(request.state, "request_id", get_request_id())
            route = getattr(request.state, "route_template", "unmatched")
            if route == "unmatched" and hasattr(request, "scope") and "endpoint" in request.scope:
                route = getattr(request.scope.get("route", None), "path", "unmatched")

            logger.info(
                "request_completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "route": route,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "error_category": error_category,
                },
            )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Enforces route-class sliding-window rate limiting.
    Employs pre-routing compiled regex classification and two-stage identity resolution.
    Returns HTTP 429 Too Many Requests on quota exhaustion with Retry-After header.
    Returns HTTP 503 on Redis infrastructure failure for fail-closed classes.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        route_template, route_class = classify_route(request.method, request.url.path)
        request.state.route_template = route_template
        request.state.route_class = route_class.value

        allowed, status_code, retry_after = await limiter.check_rate_limit(request, route_class)
        if not allowed:
            from starlette.responses import JSONResponse

            request_id = getattr(request.state, "request_id", get_request_id())

            if status_code == 429:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": f"Too many requests. Please try again in {retry_after} seconds.",
                        "retry_after": retry_after,
                        "request_id": request_id,
                        "error_category": "rate_limited",
                    },
                    headers={
                        "Retry-After": str(retry_after or 1),
                        "X-Request-ID": request_id,
                    },
                )
            elif status_code == 503:
                return JSONResponse(
                    status_code=503,
                    content={
                        "detail": "Rate limiting service temporarily unavailable.",
                        "request_id": request_id,
                        "error_category": "service_unavailable",
                    },
                    headers={"X-Request-ID": request_id},
                )

        return await call_next(request)
