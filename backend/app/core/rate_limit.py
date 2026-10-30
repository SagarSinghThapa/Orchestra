import asyncio
import hashlib
import ipaddress
import logging
import math
import re
import time
from collections import OrderedDict
from enum import Enum
from typing import Dict, List, Optional, Tuple

from fastapi import Request
from jose import JWTError

from app.auth.jwt import decode_token
from app.core.config import settings
from app.core.redis import get_redis_client

logger = logging.getLogger("orchestra.rate_limit")


class RouteClass(str, Enum):
    AUTH = "AUTH"
    UPLOAD = "UPLOAD"
    SEARCH = "SEARCH"
    RESEARCH = "RESEARCH"
    DEVELOPER = "DEVELOPER"
    ORCHESTRATOR = "ORCHESTRATOR"
    MEMORY_REBUILD = "MEMORY_REBUILD"
    EVALUATION = "EVALUATION"
    CHEAP_READ = "CHEAP_READ"
    EXEMPT = "EXEMPT"


# Authoritative Pre-Routing Regex Classifier
ROUTE_RULES: List[Tuple[re.Pattern, str, str, RouteClass]] = [
    # Exempt infrastructure routes
    (re.compile(r"^/$"), "GET", "/", RouteClass.EXEMPT),
    (re.compile(r"^/health.*$"), "GET", "/health", RouteClass.EXEMPT),
    (re.compile(r"^/metrics$"), "GET", "/metrics", RouteClass.EXEMPT),
    (re.compile(r"^/openapi\.json$"), "GET", "/openapi.json", RouteClass.EXEMPT),
    (re.compile(r"^/docs.*$"), "GET", "/docs", RouteClass.EXEMPT),
    (re.compile(r"^/redoc.*$"), "GET", "/redoc", RouteClass.EXEMPT),

    # Authentication routes
    (re.compile(r"^/auth/login$"), "POST", "/auth/login", RouteClass.AUTH),
    (re.compile(r"^/auth/register$"), "POST", "/auth/register", RouteClass.AUTH),
    (re.compile(r"^/auth/refresh$"), "POST", "/auth/refresh", RouteClass.AUTH),
    (re.compile(r"^/auth/logout$"), "POST", "/auth/logout", RouteClass.CHEAP_READ),
    (re.compile(r"^/auth/me$"), "GET", "/auth/me", RouteClass.CHEAP_READ),

    # Research and Knowledge Ingestion
    (re.compile(r"^/projects/[^/]+/documents/[^/]+/reindex$"), "POST", "/projects/{project_id}/documents/{document_id}/reindex", RouteClass.UPLOAD),
    (re.compile(r"^/projects/[^/]+/documents$"), "POST", "/projects/{project_id}/documents", RouteClass.UPLOAD),
    (re.compile(r"^/projects/[^/]+/search$"), "POST", "/projects/{project_id}/search", RouteClass.SEARCH),
    (re.compile(r"^/projects/[^/]+/research$"), "POST", "/projects/{project_id}/research", RouteClass.RESEARCH),

    # Developer Subgraph
    (re.compile(r"^/projects/[^/]+/developer$"), "POST", "/projects/{project_id}/developer", RouteClass.DEVELOPER),

    # Orchestrator Subgraph
    (re.compile(r"^/projects/[^/]+/orchestrate(?:/sessions/[^/]+)?$"), "POST", "/projects/{project_id}/orchestrate", RouteClass.ORCHESTRATOR),

    # Memory Subsystem
    (re.compile(r"^/projects/[^/]+/sessions/[^/]+/memory/rebuild$"), "POST", "/projects/{project_id}/sessions/{session_id}/memory/rebuild", RouteClass.MEMORY_REBUILD),

    # Evaluations Subsystem
    (re.compile(r"^/evaluations/runs$"), "POST", "/evaluations/runs", RouteClass.EVALUATION),
    (re.compile(r"^/evaluations/runs/[^/]+/baseline$"), "POST", "/evaluations/runs/{run_id}/baseline", RouteClass.CHEAP_READ),
]


def classify_route(method: str, path: str) -> Tuple[str, RouteClass]:
    """
    Classifies an incoming HTTP request into a normalized route template and route class
    using pre-routing compiled regex matching prior to router dispatch.
    """
    if method == "OPTIONS":
        return ("", RouteClass.EXEMPT)

    clean_path = path.rstrip("/") or "/"

    for pattern, rule_method, template, route_class in ROUTE_RULES:
        if rule_method == method and pattern.match(clean_path):
            return (template, route_class)

    # General fallback for read-heavy and metadata operations
    if clean_path.startswith(("/projects", "/sessions", "/evaluations", "/auth")):
        return (clean_path, RouteClass.CHEAP_READ)

    return ("unmatched", RouteClass.CHEAP_READ)


def normalize_client_ip(ip_str: Optional[str]) -> str:
    """
    Normalizes IPv4 and IPv6 addresses into canonical compressed strings.
    """
    if not ip_str:
        return "127.0.0.1"
    try:
        ip = ipaddress.ip_address(ip_str.strip())
        return ip.compressed
    except ValueError:
        return re.sub(r"[^a-zA-Z0-9\.\:]", "", ip_str)[:45]


def resolve_identity(request: Request, route_class: RouteClass) -> str:
    """
    Derives rate-limit identity with strict credential precedence (Bearer -> Cookie -> IP).
    Zero database lookups performed.
    Auth routes (login/register) are strictly keyed by client IP to prevent targeted account lockout DoS.
    """
    client_ip = normalize_client_ip(getattr(request.client, "host", None))

    # Login and register must never be keyed by user identifier or email
    if route_class == RouteClass.AUTH:
        return f"ip:{client_ip}"

    # Check Authorization: Bearer header precedence
    auth_header = request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            try:
                payload = decode_token(parts[1], expected_type="access")
                user_id = payload.get("sub")
                if user_id:
                    return f"user:{user_id}"
            except JWTError:
                pass
        # If header supplied was invalid, fall back to IP rather than checking cookie
        return f"ip:{client_ip}"

    # Cookie fallback only when Authorization header is absent
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        try:
            payload = decode_token(cookie_token, expected_type="access")
            user_id = payload.get("sub")
            if user_id:
                return f"user:{user_id}"
        except JWTError:
            pass

    return f"ip:{client_ip}"


REDIS_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])

-- Authoritative Redis server clock prevents multi-worker clock skew
local rtime = redis.call('TIME')
local now = tonumber(rtime[1]) + (tonumber(rtime[2]) / 1000000)
local clear_before = now - window

-- Prune expired entries
redis.call('ZREMRANGEBYSCORE', key, '-inf', clear_before)
local current_requests = redis.call('ZCARD', key)

if current_requests < limit then
    local seq = redis.call('INCR', key .. ':seq')
    local member = tostring(now) .. ':' .. tostring(seq)
    redis.call('ZADD', key, now, member)
    redis.call('EXPIRE', key, math.ceil(window) + 1)
    redis.call('EXPIRE', key .. ':seq', math.ceil(window) + 1)
    return {1, limit - current_requests - 1, 0}
else
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = 1
    if #oldest > 1 then
        retry_after = math.max(1, math.ceil(tonumber(oldest[2]) + window - now))
    end
    return {0, 0, retry_after}
end
"""


class MemoryRateLimiterStorage:
    """
    Thread-safe sliding window storage for development and offline unit testing.
    Hard bounded at 10,000 keys with LRU eviction to prevent memory exhaustion attacks.
    """

    def __init__(self, max_keys: int = 10000):
        self._max_keys = max_keys
        self._buckets: OrderedDict[str, List[float]] = OrderedDict()
        self._lock = asyncio.Lock()
        self._time_func = time.time

    def set_time_func(self, time_func):
        """Allows injecting deterministic mock clocks in tests."""
        self._time_func = time_func

    async def check_and_record(
        self, key: str, window_seconds: float, limit: int
    ) -> Tuple[bool, int, int]:
        async with self._lock:
            now = self._time_func()
            clear_before = now - window_seconds

            # Fetch or create bucket
            if key in self._buckets:
                self._buckets.move_to_end(key)
                timestamps = self._buckets[key]
            else:
                if len(self._buckets) >= self._max_keys:
                    self._buckets.popitem(last=False)
                timestamps = []
                self._buckets[key] = timestamps

            # Prune expired timestamps
            valid_timestamps = [t for t in timestamps if t > clear_before]
            self._buckets[key] = valid_timestamps

            if len(valid_timestamps) < limit:
                valid_timestamps.append(now)
                remaining = limit - len(valid_timestamps)
                return (True, remaining, 0)
            else:
                oldest = valid_timestamps[0]
                retry_after = max(1, math.ceil(oldest + window_seconds - now))
                return (False, 0, retry_after)


# Global in-memory storage instance
memory_limiter_storage = MemoryRateLimiterStorage()


class RateLimiter:
    """
    Central rate limiting coordinator enforcing sliding window limits across route classes.
    """

    def __init__(self):
        self.memory_storage = memory_limiter_storage

    def get_quota(self, route_class: RouteClass) -> Tuple[int, int]:
        """
        Returns (limit, window_seconds) based on the route class.
        """
        if route_class == RouteClass.AUTH:
            return (settings.rate_limit_auth_limit, settings.rate_limit_auth_window_seconds)
        elif route_class == RouteClass.UPLOAD:
            return (settings.rate_limit_upload_limit, settings.rate_limit_upload_window_seconds)
        elif route_class == RouteClass.SEARCH:
            return (settings.rate_limit_search_limit, settings.rate_limit_search_window_seconds)
        elif route_class in (RouteClass.RESEARCH, RouteClass.DEVELOPER, RouteClass.ORCHESTRATOR):
            return (settings.rate_limit_ai_limit, settings.rate_limit_ai_window_seconds)
        elif route_class == RouteClass.MEMORY_REBUILD:
            return (settings.rate_limit_ai_limit, settings.rate_limit_ai_window_seconds)
        elif route_class == RouteClass.EVALUATION:
            return (settings.rate_limit_eval_limit, settings.rate_limit_eval_window_seconds)
        elif route_class == RouteClass.CHEAP_READ:
            return (settings.rate_limit_read_limit, settings.rate_limit_read_window_seconds)
        return (1000, 60)

    async def check_rate_limit(
        self, request: Request, route_class: RouteClass
    ) -> Tuple[bool, int, Optional[int]]:
        """
        Checks rate quota for the current request.
        Returns: (allowed: bool, status_code: int, retry_after_seconds: Optional[int])
        """
        if not settings.rate_limit_enabled or route_class == RouteClass.EXEMPT:
            return (True, 200, None)

        limit, window = self.get_quota(route_class)
        identity = resolve_identity(request, route_class)
        identity_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
        key = f"orchestra:rl:{route_class.value}:{identity_hash}"

        use_redis = settings.rate_limit_backend == "redis"
        redis_client = get_redis_client() if use_redis else None

        if use_redis and redis_client is not None:
            try:
                res = await redis_client.eval(REDIS_SLIDING_WINDOW_LUA, 1, key, window, limit)
                allowed = bool(res[0])
                retry_after = int(res[2])
                if allowed:
                    return (True, 200, None)
                return (False, 429, retry_after)
            except Exception as e:
                logger.warning(f"Redis rate limiter failure: {e}")
                # Enforce Redis failure policy
                if route_class in (
                    RouteClass.AUTH,
                    RouteClass.RESEARCH,
                    RouteClass.DEVELOPER,
                    RouteClass.ORCHESTRATOR,
                    RouteClass.EVALUATION,
                    RouteClass.UPLOAD,
                    RouteClass.SEARCH,
                    RouteClass.MEMORY_REBUILD,
                ):
                    return (False, 503, None)
                # Fail open for CHEAP_READ
                return (True, 200, None)

        # Fallback to in-memory limiter for development/test environments
        if settings.environment in ("development", "test") or not use_redis:
            allowed, remaining, retry_after = await self.memory_storage.check_and_record(
                key, float(window), limit
            )
            if allowed:
                return (True, 200, None)
            return (False, 429, retry_after)

        # In production with Redis configured but client missing/disconnected
        if route_class != RouteClass.CHEAP_READ:
            return (False, 503, None)
        return (True, 200, None)


limiter = RateLimiter()
