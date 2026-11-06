import asyncio
import os
import pytest
import redis.asyncio as aioredis
from unittest.mock import MagicMock

from app.core.config import settings
from app.core.rate_limit import (
    REDIS_SLIDING_WINDOW_LUA,
    RateLimiter,
    RouteClass,
    limiter,
)


TEST_REDIS_URL = os.getenv(
    "TEST_REDIS_URL",
    os.getenv(
        "REDIS_URL",
        "redis://:replace_with_strong_redis_password_here@127.0.0.1:6380/0",
    ),
)


def get_test_redis_client():
    return aioredis.from_url(
        TEST_REDIS_URL,
        decode_responses=True,
        socket_timeout=5.0,
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_redis_sliding_window_lua_atomicity():
    """
    Validates that the Redis Lua sliding window script operates atomically under concurrency:
    50 concurrent coroutines attempting to consume quota with limit=10 results in exactly
    10 allowed requests and 40 rejected requests with positive retry_after values.
    """
    client = get_test_redis_client()
    key = "orchestra:test:concurrency_window"
    window = 10
    limit = 10

    # Ensure clean key before test
    await client.delete(key, f"{key}:seq")

    try:
        # Ping to assert live connection
        assert await client.ping() is True

        # Dispatch 50 concurrent requests simultaneously
        async def call_limiter():
            res = await client.eval(REDIS_SLIDING_WINDOW_LUA, 1, key, window, limit)
            # Lua returns {allowed (0/1), remaining, retry_after}
            return (bool(res[0]), int(res[1]), int(res[2]))

        results = await asyncio.gather(*[call_limiter() for _ in range(50)])

        allowed_count = sum(1 for allowed, _, _ in results if allowed)
        rejected_count = sum(1 for allowed, _, _ in results if not allowed)

        assert allowed_count == 10, f"Expected exactly 10 allowed requests, got {allowed_count}"
        assert rejected_count == 40, f"Expected exactly 40 rejected requests, got {rejected_count}"

        # Verify retry_after is positive for all rejected requests
        for allowed, remaining, retry_after in results:
            if not allowed:
                assert retry_after >= 1, f"Expected positive retry_after, got {retry_after}"

    finally:
        await client.delete(key, f"{key}:seq")
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_redis_sliding_window_key_expiration_and_ttl():
    """
    Validates that Redis sliding window sets appropriate TTL matching the window duration
    and keys expire cleanly without leaking memory in live Redis.
    """
    client = get_test_redis_client()
    key = "orchestra:test:ttl_window"
    window = 3  # Short 3-second window
    limit = 5

    await client.delete(key, f"{key}:seq")

    try:
        assert await client.ping() is True

        # Record request
        res = await client.eval(REDIS_SLIDING_WINDOW_LUA, 1, key, window, limit)
        assert res[0] == 1

        # Check TTL on key and sequence counter
        ttl_main = await client.ttl(key)
        ttl_seq = await client.ttl(f"{key}:seq")

        assert 0 < ttl_main <= window + 2, f"Unexpected main key TTL: {ttl_main}"
        assert 0 < ttl_seq <= window + 2, f"Unexpected seq key TTL: {ttl_seq}"

        # Wait for expiration
        await asyncio.sleep(window + 1.5)

        # Confirm keys expired
        exists_main = await client.exists(key)
        exists_seq = await client.exists(f"{key}:seq")
        assert exists_main == 0, "Expected main key to have expired"
        assert exists_seq == 0, "Expected seq key to have expired"

    finally:
        await client.delete(key, f"{key}:seq")
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_redis_differentiated_failure_policy():
    """
    Validates the differentiated fail-closed / fail-open rate limiting policy:
    When Redis is unreachable:
    - Auth and AI routes (AUTH, RESEARCH, DEVELOPER, ORCHESTRATOR) fail closed with HTTP 503.
    - Cheap read routes (CHEAP_READ) fail open with HTTP 200.
    """
    # Create rate limiter instance
    custom_limiter = RateLimiter()

    # Mock request
    mock_request = MagicMock()
    mock_request.client.host = "192.168.1.100"
    mock_request.headers = {}
    mock_request.cookies = {}

    # Create mock broken Redis client that raises ConnectionError on eval
    broken_redis = MagicMock()

    async def raise_conn_error(*args, **kwargs):
        raise aioredis.ConnectionError("Simulated Redis connection failure")

    broken_redis.eval = raise_conn_error

    # Temporarily force rate_limit_backend to redis and inject broken client
    orig_backend = settings.rate_limit_backend
    orig_enabled = settings.rate_limit_enabled

    try:
        settings.rate_limit_backend = "redis"
        settings.rate_limit_enabled = True

        import app.core.rate_limit as rl_module
        orig_get_client = rl_module.get_redis_client
        rl_module.get_redis_client = lambda: broken_redis

        try:
            # 1. Auth route must fail closed with 503
            allowed, status, _ = await custom_limiter.check_rate_limit(mock_request, RouteClass.AUTH)
            assert allowed is False
            assert status == 503

            # 2. Research route must fail closed with 503
            allowed, status, _ = await custom_limiter.check_rate_limit(mock_request, RouteClass.RESEARCH)
            assert allowed is False
            assert status == 503

            # 3. Developer route must fail closed with 503
            allowed, status, _ = await custom_limiter.check_rate_limit(mock_request, RouteClass.DEVELOPER)
            assert allowed is False
            assert status == 503

            # 4. Orchestrator route must fail closed with 503
            allowed, status, _ = await custom_limiter.check_rate_limit(mock_request, RouteClass.ORCHESTRATOR)
            assert allowed is False
            assert status == 503

            # 5. Cheap read route must fail open with 200
            allowed, status, _ = await custom_limiter.check_rate_limit(mock_request, RouteClass.CHEAP_READ)
            assert allowed is True
            assert status == 200

        finally:
            rl_module.get_redis_client = orig_get_client

    finally:
        settings.rate_limit_backend = orig_backend
        settings.rate_limit_enabled = orig_enabled
