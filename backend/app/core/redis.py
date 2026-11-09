import logging
from typing import Optional
import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger("orchestra.redis")

_redis_pool: Optional[aioredis.ConnectionPool] = None
_redis_client: Optional[aioredis.Redis] = None


async def init_redis_pool() -> None:
    """
    Initializes the asynchronous Redis connection pool and validates connectivity.
    Degrades gracefully (fails soft) if Redis is unconfigured or unreachable.
    """
    global _redis_pool, _redis_client

    if not settings.redis_url:
        logger.info("REDIS_URL is not configured; running with Redis disabled.")
        return

    try:
        _redis_pool = aioredis.ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
        )
        _redis_client = aioredis.Redis(connection_pool=_redis_pool)
        await _redis_client.ping()
        logger.info("Connected to Redis successfully.")
    except Exception as e:
        logger.warning(
            f"Unable to connect to Redis at {settings.redis_url}: {e}. "
            "Operating in degraded mode with Redis unavailable."
        )
        if _redis_client is not None:
            await _redis_client.aclose()
        if _redis_pool is not None:
            await _redis_pool.disconnect()
        _redis_client = None
        _redis_pool = None


async def close_redis_pool() -> None:
    """
    Closes the Redis client connection and connection pool cleanly upon application shutdown.
    """
    global _redis_pool, _redis_client

    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except Exception as e:
            logger.warning(f"Error closing Redis client: {e}")
        _redis_client = None

    if _redis_pool is not None:
        try:
            await _redis_pool.disconnect()
        except Exception as e:
            logger.warning(f"Error disconnecting Redis connection pool: {e}")
        _redis_pool = None


def get_redis_client() -> Optional[aioredis.Redis]:
    """
    Returns the active Redis client, or None if Redis is unconfigured or disconnected.
    """
    return _redis_client


async def get_redis_health() -> dict:
    """
    Returns the operational health status of the Redis infrastructure.
    Safe to call in health check routes without raising unhandled exceptions.
    """
    if not settings.redis_url:
        return {
            "redis": "unconfigured",
            "status": "disabled",
        }

    if _redis_client is None:
        return {
            "redis": "disconnected",
            "status": "unhealthy",
            "error": "Redis client is not connected",
        }

    try:
        await _redis_client.ping()
        return {
            "redis": "connected",
            "status": "healthy",
        }
    except Exception as e:
        return {
            "redis": "disconnected",
            "status": "unhealthy",
            "error": str(e),
        }
