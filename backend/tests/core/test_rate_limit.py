import asyncio
import time
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.core.config import settings
from app.core.middleware import RateLimitMiddleware, RequestIDMiddleware
from app.core.rate_limit import (
    MemoryRateLimiterStorage,
    RateLimiter,
    RouteClass,
    classify_route,
    normalize_client_ip,
    resolve_identity,
)


def test_classify_route_authoritative_paths():
    # Auth
    assert classify_route("POST", "/auth/login") == ("/auth/login", RouteClass.AUTH)
    assert classify_route("POST", "/auth/register") == ("/auth/register", RouteClass.AUTH)
    assert classify_route("POST", "/auth/refresh") == ("/auth/refresh", RouteClass.AUTH)
    assert classify_route("POST", "/auth/logout") == ("/auth/logout", RouteClass.CHEAP_READ)
    assert classify_route("GET", "/auth/me") == ("/auth/me", RouteClass.CHEAP_READ)

    # Ingestion & Search
    assert classify_route("POST", "/projects/42/documents") == (
        "/projects/{project_id}/documents",
        RouteClass.UPLOAD,
    )
    assert classify_route("POST", "/projects/42/documents/10/reindex") == (
        "/projects/{project_id}/documents/{document_id}/reindex",
        RouteClass.UPLOAD,
    )
    assert classify_route("POST", "/projects/42/search") == (
        "/projects/{project_id}/search",
        RouteClass.SEARCH,
    )

    # Expensive AI Subgraphs
    assert classify_route("POST", "/projects/42/research") == (
        "/projects/{project_id}/research",
        RouteClass.RESEARCH,
    )
    assert classify_route("POST", "/projects/42/developer") == (
        "/projects/{project_id}/developer",
        RouteClass.DEVELOPER,
    )
    assert classify_route("POST", "/projects/42/orchestrate") == (
        "/projects/{project_id}/orchestrate",
        RouteClass.ORCHESTRATOR,
    )
    assert classify_route("POST", "/projects/42/orchestrate/sessions/99") == (
        "/projects/{project_id}/orchestrate",
        RouteClass.ORCHESTRATOR,
    )
    assert classify_route("POST", "/projects/42/sessions/99/memory/rebuild") == (
        "/projects/{project_id}/sessions/{session_id}/memory/rebuild",
        RouteClass.MEMORY_REBUILD,
    )
    assert classify_route("POST", "/evaluations/runs") == (
        "/evaluations/runs",
        RouteClass.EVALUATION,
    )

    # Exempt
    assert classify_route("OPTIONS", "/anything") == ("", RouteClass.EXEMPT)
    assert classify_route("GET", "/") == ("/", RouteClass.EXEMPT)
    assert classify_route("GET", "/health") == ("/health", RouteClass.EXEMPT)
    assert classify_route("GET", "/health/ready") == ("/health", RouteClass.EXEMPT)
    assert classify_route("GET", "/metrics") == ("/metrics", RouteClass.EXEMPT)


def test_normalize_client_ip():
    assert normalize_client_ip("127.0.0.1") == "127.0.0.1"
    assert normalize_client_ip("192.168.1.100") == "192.168.1.100"
    # Canonical IPv6 compression
    assert normalize_client_ip("2001:0db8:0000:0000:0000:0000:0000:0001") == "2001:db8::1"
    assert normalize_client_ip(None) == "127.0.0.1"


@pytest.mark.asyncio
async def test_memory_sliding_window_algorithm():
    storage = MemoryRateLimiterStorage(max_keys=10)
    current_time = 1000.0
    storage.set_time_func(lambda: current_time)

    key = "test_key"
    window = 60.0
    limit = 3

    # First 3 requests allowed
    ok1, rem1, retry1 = await storage.check_and_record(key, window, limit)
    assert ok1 is True
    assert rem1 == 2

    ok2, rem2, retry2 = await storage.check_and_record(key, window, limit)
    assert ok2 is True
    assert rem2 == 1

    ok3, rem3, retry3 = await storage.check_and_record(key, window, limit)
    assert ok3 is True
    assert rem3 == 0

    # 4th request rejected
    ok4, rem4, retry4 = await storage.check_and_record(key, window, limit)
    assert ok4 is False
    assert rem4 == 0
    assert retry4 == 60  # (1000 + 60) - 1000

    # Advance time by 30s -> still rejected, retry_after is 30s
    current_time = 1030.0
    ok5, rem5, retry5 = await storage.check_and_record(key, window, limit)
    assert ok5 is False
    assert retry5 == 30

    # Advance time past 60s -> allowed again!
    current_time = 1061.0
    ok6, rem6, retry6 = await storage.check_and_record(key, window, limit)
    assert ok6 is True
    assert rem6 == 2


@pytest.mark.asyncio
async def test_memory_limiter_lru_eviction():
    storage = MemoryRateLimiterStorage(max_keys=3)
    current_time = 100.0
    storage.set_time_func(lambda: current_time)

    # Fill 3 keys
    await storage.check_and_record("k1", 60.0, 5)
    await storage.check_and_record("k2", 60.0, 5)
    await storage.check_and_record("k3", 60.0, 5)
    assert len(storage._buckets) == 3

    # Adding 4th key evicts the least recently used ("k1")
    await storage.check_and_record("k4", 60.0, 5)
    assert len(storage._buckets) == 3
    assert "k1" not in storage._buckets
    assert "k4" in storage._buckets


def test_identity_resolution_precedence(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", "test_jwt_secret_key_12345")
    # Helper mock request
    class MockClient:
        host = "192.168.1.50"

    class MockRequest:
        client = MockClient()
        headers = {}
        cookies = {}

    req = MockRequest()

    # 1. Auth routes strictly keyed by IP
    assert resolve_identity(req, RouteClass.AUTH) == "ip:192.168.1.50"

    # 2. Unauthenticated request keyed by IP
    assert resolve_identity(req, RouteClass.CHEAP_READ) == "ip:192.168.1.50"

    # 3. Valid Bearer Token resolves to user ID
    token = create_access_token(42, role="member")
    req.headers = {"Authorization": f"Bearer {token}"}
    assert resolve_identity(req, RouteClass.RESEARCH) == "user:42"

    # 4. Header precedence over cookie
    cookie_token = create_access_token(99, role="member")
    req.cookies = {"access_token": cookie_token}
    # Still resolves to 42 because Authorization header has precedence
    assert resolve_identity(req, RouteClass.RESEARCH) == "user:42"

    # 5. Cookie evaluated only when header absent
    req.headers = {}
    assert resolve_identity(req, RouteClass.RESEARCH) == "user:99"

    # 6. Invalid token falls back to IP
    req.headers = {"Authorization": "Bearer invalid_garbage_token"}
    req.cookies = {}
    assert resolve_identity(req, RouteClass.RESEARCH) == "ip:192.168.1.50"


def test_fastapi_rate_limit_integration(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_backend", "memory")
    monkeypatch.setattr(settings, "environment", "test")

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestIDMiddleware)

    @app.post("/auth/login")
    def login():
        return {"status": "ok"}

    @app.options("/auth/login")
    def preflight():
        return {"status": "preflight_ok"}

    client = TestClient(app, raise_server_exceptions=False)

    # OPTIONS preflight must never be rate-limited
    for _ in range(15):
        resp = client.options("/auth/login")
        assert resp.status_code == 200

    # AUTH limit is 5 requests per 60s
    for i in range(5):
        resp = client.post("/auth/login")
        assert resp.status_code == 200, f"Request {i+1} failed unexpectedly"

    # 6th request must trigger HTTP 429
    resp_429 = client.post("/auth/login")
    assert resp_429.status_code == 429
    assert "Retry-After" in resp_429.headers
    assert "X-Request-ID" in resp_429.headers
    data = resp_429.json()
    assert data["error_category"] == "rate_limited"
    assert "Too many requests" in data["detail"]
    assert data["retry_after"] >= 1


@pytest.mark.asyncio
async def test_redis_failure_policy_differentiated():
    limiter = RateLimiter()

    class MockRedisFailing:
        async def eval(self, *args, **kwargs):
            raise ConnectionError("Simulated Redis outage")

    class MockRequest:
        client = type("Client", (), {"host": "10.0.0.1"})()
        headers = {}
        cookies = {}

    req = MockRequest()

    # Simulate production Redis mode with failing client
    orig_backend = settings.rate_limit_backend
    settings.rate_limit_backend = "redis"
    try:
        from unittest.mock import patch

        with patch("app.core.rate_limit.get_redis_client", return_value=MockRedisFailing()):
            # AUTH -> Fail-Closed (503)
            allowed, status_code, _ = await limiter.check_rate_limit(req, RouteClass.AUTH)
            assert allowed is False
            assert status_code == 503

            # RESEARCH -> Fail-Closed (503)
            allowed, status_code, _ = await limiter.check_rate_limit(req, RouteClass.RESEARCH)
            assert allowed is False
            assert status_code == 503

            # CHEAP_READ -> Fail-Open (200)
            allowed, status_code, _ = await limiter.check_rate_limit(req, RouteClass.CHEAP_READ)
            assert allowed is True
            assert status_code == 200
    finally:
        settings.rate_limit_backend = orig_backend
