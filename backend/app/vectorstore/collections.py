"""Qdrant collection management – creation, deletion, and schema."""

from __future__ import annotations

from qdrant_client.http.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    SparseIndexParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchAny,
    MatchValue,
    SearchRequest,
    NamedVector,
    NamedSparseVector,
    SparseVector,
    models,
)

from app.core.config import get_settings
from app.core.logging import get_logger
from app.vectorstore.qdrant_client import get_qdrant_client

logger = get_logger(__name__)

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"

_collection_ready: set[str] = set()


def ensure_collection() -> None:
    """Create the documents collection if it doesn't exist, with hybrid search vectors."""
    settings = get_settings()
    client = get_qdrant_client()
    collection_name = settings.QDRANT_COLLECTION

    if collection_name in _collection_ready:
        return

    collections = [c.name for c in client.get_collections().collections]
    if collection_name in collections:
        _collection_ready.add(collection_name)
        logger.info("collection_exists", collection=collection_name)
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config={
            DENSE_VECTOR_NAME: VectorParams(
                size=settings.EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        },
        sparse_vectors_config={
            SPARSE_VECTOR_NAME: SparseVectorParams(
                index=SparseIndexParams(on_disk=False),
            ),
        },
    )

    # Create payload indexes for filtering
    client.create_payload_index(
        collection_name=collection_name,
        field_name="user_id",
        field_schema="integer",
    )
    client.create_payload_index(
        collection_name=collection_name,
        field_name="document_id",
        field_schema="keyword",
    )

    _collection_ready.add(collection_name)
    logger.info("collection_created", collection=collection_name)


def delete_collection() -> None:
    """Delete the documents collection."""
    settings = get_settings()
    client = get_qdrant_client()
    client.delete_collection(settings.QDRANT_COLLECTION)
    _collection_ready.discard(settings.QDRANT_COLLECTION)
    logger.info("collection_deleted", collection=settings.QDRANT_COLLECTION)


def upsert_chunks(
    chunks: list[dict],
    dense_vectors: list[list[float]],
    sparse_vectors: list[dict] | None = None,
    user_id: int = 0,
) -> None:
    """Upsert document chunks with their embeddings into Qdrant.
    
    Args:
        chunks: List of dicts with keys: chunk_id, text, document_id, page_number, chunk_index, metadata.
        dense_vectors: Dense embedding vectors aligned with chunks.
        sparse_vectors: Optional sparse vectors (BM25) for hybrid search. Each is {"indices": [...], "values": [...]}.
        user_id: Owner user ID for multi-tenant filtering.
    """
    settings = get_settings()
    client = get_qdrant_client()

    points = []
    for i, chunk in enumerate(chunks):
        vectors = {DENSE_VECTOR_NAME: dense_vectors[i]}
        
        point_kwargs = {
            "id": chunk["chunk_id"],
            "payload": {
                "text": chunk["text"],
                "document_id": chunk["document_id"],
                "page_number": chunk["page_number"],
                "chunk_index": chunk["chunk_index"],
                "user_id": user_id,
                **chunk.get("metadata", {}),
            },
        }

        if sparse_vectors and i < len(sparse_vectors):
            sv = sparse_vectors[i]
            point_kwargs["vector"] = {
                DENSE_VECTOR_NAME: dense_vectors[i],
                SPARSE_VECTOR_NAME: SparseVector(
                    indices=sv["indices"],
                    values=sv["values"],
                ),
            }
        else:
            point_kwargs["vector"] = {DENSE_VECTOR_NAME: dense_vectors[i]}

        points.append(PointStruct(**point_kwargs))

    # Batch upsert in groups of 100
    batch_size = 100
    for batch_start in range(0, len(points), batch_size):
        batch = points[batch_start : batch_start + batch_size]
        client.upsert(collection_name=settings.QDRANT_COLLECTION, points=batch)

    logger.info(
        "upserted_chunks",
        count=len(points),
        collection=settings.QDRANT_COLLECTION,
    )


def delete_document_vectors(document_id: str, user_id: int) -> None:
    """Delete all vectors for a given document (filtered by user_id for safety)."""
    settings = get_settings()
    client = get_qdrant_client()

    client.delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=models.FilterSelector(
            filter=Filter(
                must=[
                    FieldCondition(key="document_id", match=MatchValue(value=document_id)),
                    FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                ]
            )
        ),
        wait=True,
    )
    logger.info("deleted_document_vectors", document_id=document_id, user_id=user_id)


def delete_user_vectors(user_id: int) -> None:
    """Delete all vectors for a user (clears orphans from deleted documents)."""
    settings = get_settings()
    client = get_qdrant_client()

    client.delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=models.FilterSelector(
            filter=Filter(
                must=[
                    FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                ]
            )
        ),
        wait=True,
    )
    logger.info("deleted_user_vectors", user_id=user_id)


def search_vectors(
    dense_vector: list[float],
    user_id: int,
    *,
    top_k: int = 10,
    document_id: str | None = None,
    document_ids: list[str] | None = None,
) -> list[dict]:
    """Search for similar chunks using dense vector with user_id filtering.
    
    Returns list of dicts with keys: chunk_id, score, text, document_id, page_number, chunk_index, metadata.

    When ``document_ids`` is provided, only search within those document IDs
    (allow-list of currently indexed docs). Empty list returns no results.
    """
    settings = get_settings()
    client = get_qdrant_client()

    if document_ids is not None and len(document_ids) == 0:
        return []

    must_conditions = [
        FieldCondition(key="user_id", match=MatchValue(value=user_id)),
    ]
    if document_id:
        must_conditions.append(
            FieldCondition(key="document_id", match=MatchValue(value=document_id)),
        )
    elif document_ids is not None:
        must_conditions.append(
            FieldCondition(key="document_id", match=MatchAny(any=document_ids)),
        )

    results = client.search(
        collection_name=settings.QDRANT_COLLECTION,
        query_vector=(DENSE_VECTOR_NAME, dense_vector),
        query_filter=Filter(must=must_conditions),
        limit=top_k,
        with_payload=True,
    )

    return [
        {
            "chunk_id": str(hit.id),
            "score": hit.score,
            "text": hit.payload.get("text", ""),
            "document_id": hit.payload.get("document_id", ""),
            "page_number": hit.payload.get("page_number", 0),
            "chunk_index": hit.payload.get("chunk_index", 0),
            "metadata": {
                k: v for k, v in hit.payload.items()
                if k not in ("text", "document_id", "page_number", "chunk_index", "user_id")
            },
        }
        for hit in results
    ]


def list_document_chunks(
    user_id: int,
    document_ids: list[str],
    *,
    limit: int = 40,
) -> list[dict]:
    """Scroll chunks for the given documents (page order) for broad summaries.

    Used when the user asks to summarize a whole document — semantic top-k alone
    often returns only a few pages.
    """
    if not document_ids or limit <= 0:
        return []

    settings = get_settings()
    client = get_qdrant_client()

    must_conditions = [
        FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        FieldCondition(key="document_id", match=MatchAny(any=document_ids)),
    ]

    collected: list[dict] = []
    next_offset = None
    # Over-fetch then sort/trim so we cover early + later pages.
    fetch_cap = min(max(limit * 3, limit), 200)

    while len(collected) < fetch_cap:
        records, next_offset = client.scroll(
            collection_name=settings.QDRANT_COLLECTION,
            scroll_filter=Filter(must=must_conditions),
            limit=min(64, fetch_cap - len(collected)),
            offset=next_offset,
            with_payload=True,
            with_vectors=False,
        )
        if not records:
            break
        for rec in records:
            payload = rec.payload or {}
            collected.append(
                {
                    "chunk_id": str(rec.id),
                    "score": 1.0,  # structural coverage, not semantic
                    "text": payload.get("text", ""),
                    "document_id": payload.get("document_id", ""),
                    "page_number": payload.get("page_number", 0),
                    "chunk_index": payload.get("chunk_index", 0),
                    "metadata": {
                        k: v
                        for k, v in payload.items()
                        if k not in ("text", "document_id", "page_number", "chunk_index", "user_id")
                    },
                }
            )
        if next_offset is None:
            break

    collected.sort(
        key=lambda c: (
            str(c.get("document_id", "")),
            int(c.get("page_number") or 0),
            int(c.get("chunk_index") or 0),
        )
    )

    # Evenly sample across the document when we have more chunks than the limit.
    if len(collected) <= limit:
        return collected
    step = len(collected) / limit
    sampled = [collected[int(i * step)] for i in range(limit)]
    # Always include first and last for intro/conclusion coverage.
    sampled[0] = collected[0]
    sampled[-1] = collected[-1]
    # Deduplicate while preserving order
    seen: set[str] = set()
    out: list[dict] = []
    for chunk in sampled:
        cid = chunk["chunk_id"]
        if cid not in seen:
            seen.add(cid)
            out.append(chunk)
    return out
