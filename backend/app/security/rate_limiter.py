"""Per-user / per-IP rate limiting via Redis with in-memory fallback."""

from __future__ import annotations

import threading
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Sliding-window rate limiter (Redis preferred, process-local memory fallback)."""

    def __init__(self, requests_per_minute: int | None = None) -> None:
        self._limit = requests_per_minute
        self._redis = None
        self._redis_checked = False
        self._memory: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _get_limit(self) -> int:
        if self._limit is not None:
            return self._limit
        return get_settings().RATE_LIMIT_PER_MINUTE

    def _get_redis(self):
        if self._redis_checked:
            return self._redis
        self._redis_checked = True
        try:
            import redis

            settings = get_settings()
            client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            client.ping()
            self._redis = client
        except Exception:
            logger.warning("rate_limiter_redis_unavailable_using_memory")
            self._redis = None
        return self._redis

    def _raise_limited(self, limit: int) -> None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Max {limit} requests per minute.",
            headers={"Retry-After": "60"},
        )

    def _check_memory(self, key: str, limit: int) -> None:
        now = time.time()
        window_start = now - 60
        with self._lock:
            stamps = [t for t in self._memory[key] if t > window_start]
            stamps.append(now)
            self._memory[key] = stamps
            if len(stamps) > limit:
                logger.warning("rate_limit_exceeded", key=key, count=len(stamps), limit=limit)
                self._raise_limited(limit)

    def _check_redis(self, r, key: str, limit: int) -> None:
        now = time.time()
        window_start = now - 60
        redis_key = f"ratelimit:{key}"
        pipe = r.pipeline()
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zadd(redis_key, {str(now): now})
        pipe.zcard(redis_key)
        pipe.expire(redis_key, 120)
        results = pipe.execute()
        count = results[2]
        if count > limit:
            logger.warning("rate_limit_exceeded", key=key, count=count, limit=limit)
            self._raise_limited(limit)

    async def check(self, key: str, *, limit: int | None = None) -> None:
        """Raise HTTP 429 when the key exceeds the configured window limit."""
        effective = limit if limit is not None else self._get_limit()
        r = self._get_redis()
        if r is not None:
            try:
                self._check_redis(r, key, effective)
                return
            except HTTPException:
                raise
            except Exception:
                logger.exception("rate_limiter_redis_error_fallback_memory")
                self._redis = None
        self._check_memory(key, effective)


rate_limiter = RateLimiter()
auth_rate_limiter = RateLimiter()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _rate_limit_key(request: Request) -> str:
    user = getattr(request.state, "user", None)
    if user is not None and hasattr(user, "id"):
        return f"user:{user.id}"
    return f"ip:{_client_ip(request)}"


async def check_rate_limit(request: Request) -> None:
    """General API rate limit (authenticated user id when present, else IP)."""
    await rate_limiter.check(_rate_limit_key(request))


async def check_auth_rate_limit(request: Request) -> None:
    """Stricter limit for login/register/refresh/OAuth start."""
    settings = get_settings()
    await auth_rate_limiter.check(
        f"auth:{_client_ip(request)}",
        limit=settings.AUTH_RATE_LIMIT_PER_MINUTE,
    )
