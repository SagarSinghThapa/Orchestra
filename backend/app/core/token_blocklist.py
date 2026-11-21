import hashlib
import logging
import time
from typing import Optional, Union
from jose import jwt

from app.core.config import settings
from app.core.redis import get_redis_client

logger = logging.getLogger("orchestra.token_blocklist")

# In-memory store permitted strictly for isolated development and tests
_memory_revocation_store: dict[str, float] = {}


class TokenRevocationError(Exception):
    """Raised when token revocation status cannot be verified securely."""
    pass


def extract_token_identifier(token_str: str) -> tuple[str, int]:
    """
    Extracts the unique token identifier (jti or SHA-256 hash) and remaining TTL.
    Decodes without enforcing expiration so that expiring tokens can still be revoked.
    """
    if not token_str:
        return "", 0

    try:
        payload = jwt.decode(
            token_str,
            settings.jwt_secret,
            algorithms=["HS256"],
            options={"verify_exp": False},
        )
        jti = payload.get("jti")
        token_id = jti if jti else hashlib.sha256(token_str.encode()).hexdigest()
        exp = payload.get("exp", 0)
        remaining_ttl = max(0, int(exp - time.time()))
        return token_id, remaining_ttl
    except Exception as e:
        logger.warning(f"Failed to decode token for identifier extraction: {e}")
        token_id = hashlib.sha256(token_str.encode()).hexdigest()
        return token_id, 3600  # Default 1 hour fallback TTL


async def revoke_token(token_str: str) -> bool:
    """
    Revokes a JWT token for the duration of its remaining lifetime.
    In production: fails closed if Redis is unavailable.
    In non-production: falls back to in-memory store.
    """
    if not token_str:
        return True

    token_id, ttl = extract_token_identifier(token_str)
    if not token_id or ttl <= 0:
        return True

    key = f"orchestra:revoked_token:{token_id}"
    redis_client = get_redis_client()

    if redis_client is not None:
        try:
            await redis_client.setex(key, ttl, "1")
            return True
        except Exception as e:
            logger.error(f"Failed to record token revocation in Redis: {e}")
            if settings.environment.lower() == "production":
                raise TokenRevocationError("Token revocation store unavailable in production") from e

    if settings.environment.lower() == "production":
        raise TokenRevocationError("Redis revocation store unavailable in production")

    # In-memory fallback permitted ONLY for isolated development and tests
    _memory_revocation_store[token_id] = time.time() + ttl
    _cleanup_memory_store()
    return True


async def is_token_revoked(token_id_or_str: str) -> bool:
    """
    Checks whether a token or its identifier has been revoked.
    In production: fails securely by raising TokenRevocationError if Redis is unavailable.
    In non-production: falls back to in-memory store.
    """
    if not token_id_or_str:
        return False

    # Normalize to identifier
    if len(token_id_or_str) > 64 and "." in token_id_or_str:
        token_id, _ = extract_token_identifier(token_id_or_str)
    else:
        token_id = token_id_or_str

    if not token_id:
        return False

    key = f"orchestra:revoked_token:{token_id}"
    redis_client = get_redis_client()

    if redis_client is not None:
        try:
            val = await redis_client.get(key)
            return val is not None
        except Exception as e:
            logger.error(f"Failed to check token revocation in Redis: {e}")
            if settings.environment.lower() == "production":
                raise TokenRevocationError("Token revocation store unavailable in production") from e

    if settings.environment.lower() == "production":
        raise TokenRevocationError("Redis revocation store unavailable in production")

    # In-memory fallback for development and tests
    expiry = _memory_revocation_store.get(token_id)
    if expiry is not None:
        if time.time() < expiry:
            return True
        else:
            _memory_revocation_store.pop(token_id, None)
    return False


def _cleanup_memory_store() -> None:
    now = time.time()
    expired = [k for k, exp in _memory_revocation_store.items() if now >= exp]
    for k in expired:
        _memory_revocation_store.pop(k, None)


def reset_memory_revocation_store() -> None:
    """Utility for test suites to clear in-memory revocations between test runs."""
    _memory_revocation_store.clear()
