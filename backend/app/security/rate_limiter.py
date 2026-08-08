"""Per-user rate limiting via Redis."""

from __future__ import annotations

import time

from fastapi import Request, HTTPException, status

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Sliding-window rate limiter backed by Redis."""

    def __init__(self, requests_per_minute: int | None = None) -> None:
        self._limit = requests_per_minute
        self._redis = None

    def _get_redis(self):
        if self._redis is None:
            try:
                import redis
                settings = get_settings()
                self._redis = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=2,
                )
            except Exception:
                logger.warning("rate_limiter_redis_unavailable")
                return None
        return self._redis

    def _get_limit(self) -> int:
        if self._limit is not None:
            return self._limit
        return get_settings().RATE_LIMIT_PER_MINUTE

    async def check(self, key: str) -> None:
        """Check rate limit for a given key. Raises HTTPException(429) if exceeded."""
        r = self._get_redis()
        if r is None:
            return

        limit = self._get_limit()
        now = time.time()
        window_start = now - 60
        redis_key = f"ratelimit:{key}"

        try:
            pipe = r.pipeline()
            pipe.zremrangebyscore(redis_key, 0, window_start)
            pipe.zadd(redis_key, {str(now): now})
            pipe.zcard(redis_key)
            pipe.expire(redis_key, 120)
            results = pipe.execute()

            count = results[2]
            if count > limit:
                logger.warning("rate_limit_exceeded", key=key, count=count, limit=limit)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Max {limit} requests per minute.",
                    headers={"Retry-After": "60"},
                )
        except HTTPException:
            raise
        except Exception:
            logger.exception("rate_limiter_error")


rate_limiter = RateLimiter()


async def check_rate_limit(request: Request) -> None:
    """FastAPI dependency for rate limiting based on authenticated user or IP."""
    user = getattr(request.state, "user", None)
    if user and hasattr(user, "id"):
        key = f"user:{user.id}"
    else:
        forwarded = request.headers.get("X-Forwarded-For")
        ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
        key = f"ip:{ip}"

    await rate_limiter.check(key)
