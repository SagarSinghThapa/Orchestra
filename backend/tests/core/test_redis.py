from unittest.mock import AsyncMock, patch
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.redis import (
    init_redis_pool,
    close_redis_pool,
    get_redis_client,
    get_redis_health,
)


@pytest.mark.asyncio
async def test_redis_lifecycle_unconfigured():
    """Verifies that Redis initializes cleanly and reports disabled when REDIS_URL is not configured."""
    original_url = settings.redis_url
    try:
        settings.redis_url = None
        await init_redis_pool()
        assert get_redis_client() is None

        health = await get_redis_health()
        assert health["redis"] == "unconfigured"
        assert health["status"] == "disabled"

        await close_redis_pool()
    finally:
        settings.redis_url = original_url


@pytest.mark.asyncio
async def test_redis_unreachable_graceful_fallback():
    """Verifies that Redis connection failures fail-soft without raising unhandled exceptions."""
    original_url = settings.redis_url
    try:
        settings.redis_url = "redis://127.0.0.1:59999/0"
        # Must not raise an exception
        await init_redis_pool()
        assert get_redis_client() is None

        # Health check must report disconnected / unhealthy
        health = await get_redis_health()
        assert health["redis"] == "disconnected"
        assert health["status"] == "unhealthy"
        assert "error" in health

        await close_redis_pool()
    finally:
        settings.redis_url = original_url


@pytest.mark.asyncio
async def test_redis_mock_healthy_status():
    """Verifies get_redis_health when Redis ping succeeds."""
    mock_client = AsyncMock()
    mock_client.ping = AsyncMock(return_value=True)

    with patch("app.core.redis.settings.redis_url", "redis://localhost:6379/0"):
        with patch("app.core.redis._redis_client", mock_client):
            health = await get_redis_health()
            assert health["redis"] == "connected"
            assert health["status"] == "healthy"


def test_redis_health_http_endpoint(client: TestClient):
    """Verifies that GET /health/redis returns valid HTTP 200 with health schema."""
    response = client.get("/health/redis")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "redis" in data
    assert "status" in data
