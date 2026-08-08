"""Health check endpoint with dependency status."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/health")
async def health_check():
    settings = get_settings()
    checks: dict[str, str] = {}

    try:
        from qdrant_client import QdrantClient

        qc = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT, timeout=3)
        qc.get_collections()
        checks["qdrant"] = "healthy"
        qc.close()
    except Exception as exc:
        logger.warning("qdrant_health_failed", error=str(exc))
        checks["qdrant"] = "unhealthy"

    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=3)
        await r.ping()
        await r.aclose()
        checks["redis"] = "healthy"
    except Exception as exc:
        logger.warning("redis_health_failed", error=str(exc))
        checks["redis"] = "unhealthy"

    overall = "healthy" if all(v == "healthy" for v in checks.values()) else "degraded"
    return {"status": overall, "services": checks}
