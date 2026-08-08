"""Qdrant client wrapper with connection management."""

from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, SparseVectorParams, SparseIndexParams

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    """Return a singleton Qdrant client."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            api_key=settings.QDRANT_API_KEY,
            prefer_grpc=True,
            grpc_port=settings.QDRANT_GRPC_PORT,
        )
        logger.info(
            "qdrant_connected",
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
        )
    return _client


def close_qdrant_client() -> None:
    """Close the Qdrant client connection."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("qdrant_disconnected")
