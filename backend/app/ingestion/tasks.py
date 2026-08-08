"""Celery background tasks for document ingestion."""

from __future__ import annotations

import uuid

from celery import current_task

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_task_engine = None


def _run_sync_db(coro):
    """Run an async coroutine synchronously for Celery tasks."""
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def _get_task_engine():
    """Reuse one async engine per worker process (avoids open/dispose per status update)."""
    global _task_engine
    if _task_engine is not None:
        return _task_engine

    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import create_async_engine

    settings = get_settings()
    kwargs: dict = {}
    if settings.DATABASE_URL.startswith("sqlite"):
        kwargs["connect_args"] = {"timeout": 30}
    engine = create_async_engine(settings.DATABASE_URL, **kwargs)
    if settings.DATABASE_URL.startswith("sqlite"):

        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # noqa: ARG001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

    _task_engine = engine
    return _task_engine


def _update_status(document_id: str, status: str, **kwargs):
    """Update document status in the database."""
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker

    from app.database.models import Document

    async def _do_update():
        engine = _get_task_engine()
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            values = {"status": status, **kwargs}
            stmt = update(Document).where(Document.id == document_id).values(**values)
            await session.execute(stmt)
            await session.commit()

    _run_sync_db(_do_update())


def _document_exists(document_id: str, user_id: int) -> bool:
    """Return True if the document row still exists for this user."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker

    from app.database.models import Document

    async def _do_check() -> bool:
        engine = _get_task_engine()
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            result = await session.execute(
                select(Document.id).where(
                    Document.id == document_id,
                    Document.user_id == user_id,
                )
            )
            return result.scalar_one_or_none() is not None

    return bool(_run_sync_db(_do_check()))


try:
    from celery_app import celery
except ImportError:
    from celery import Celery
    celery = Celery()


@celery.task(bind=True, name="app.ingestion.tasks.ingest_document", max_retries=2)
def ingest_document(self, document_id: str, file_path: str, user_id: int) -> dict:
    """Parse, chunk, embed, and store a document in the vector database.

    This runs as a Celery background task triggered after file upload.
    """
    logger.info("ingestion_started", document_id=document_id, file_path=file_path)

    try:
        if not _document_exists(document_id, user_id):
            logger.warning(
                "ingestion_aborted_document_missing",
                document_id=document_id,
                user_id=user_id,
            )
            return {
                "document_id": document_id,
                "status": "aborted",
                "reason": "document_deleted",
            }

        _update_status(document_id, "processing")
        if self.request.id:
            self.update_state(state="PROCESSING", meta={"step": "parsing"})

        # Step 1: Parse document
        from app.ingestion.parser import parse_document
        pages = parse_document(file_path)

        if not pages:
            _update_status(document_id, "completed", chunk_count=0)
            logger.warning("ingestion_no_content", document_id=document_id)
            return {"document_id": document_id, "chunks": 0, "status": "completed"}

        if self.request.id:
            self.update_state(state="PROCESSING", meta={"step": "chunking", "pages": len(pages)})

        # Step 2: Chunk pages
        from app.rag.chunking import chunk_pages
        page_dicts = [
            {"text": p.text, "page_number": p.page_number, "metadata": p.metadata}
            for p in pages
        ]
        chunks = chunk_pages(page_dicts, document_id)

        if not chunks:
            _update_status(document_id, "completed", chunk_count=0)
            return {"document_id": document_id, "chunks": 0, "status": "completed"}

        if self.request.id:
            self.update_state(
                state="PROCESSING",
                meta={"step": "embedding", "chunks": len(chunks)},
            )

        # Step 3: Generate embeddings (provider handles batching internally)
        from app.ingestion.embeddings import get_embedder
        embedder = get_embedder()
        texts = [c.text for c in chunks]
        all_vectors = embedder.embed_texts(texts)

        if self.request.id:
            self.update_state(
                state="PROCESSING",
                meta={"step": "storing", "vectors": len(all_vectors)},
            )

        # Abort if the user deleted the document while we were embedding
        if not _document_exists(document_id, user_id):
            logger.warning(
                "ingestion_aborted_before_upsert",
                document_id=document_id,
                user_id=user_id,
            )
            return {
                "document_id": document_id,
                "status": "aborted",
                "reason": "document_deleted",
            }

        # Step 4: Ensure collection exists and upsert
        from app.vectorstore.collections import ensure_collection, upsert_chunks
        ensure_collection()

        chunk_dicts = [
            {
                "chunk_id": str(uuid.uuid4()),
                "text": c.text,
                "document_id": c.document_id,
                "page_number": c.page_number,
                "chunk_index": c.chunk_index,
                "metadata": c.metadata,
            }
            for c in chunks
        ]

        upsert_chunks(chunk_dicts, all_vectors, user_id=user_id)

        # Step 5: Update document status
        _update_status(document_id, "completed", chunk_count=len(chunks))

        logger.info(
            "ingestion_completed",
            document_id=document_id,
            pages=len(pages),
            chunks=len(chunks),
        )
        return {
            "document_id": document_id,
            "pages": len(pages),
            "chunks": len(chunks),
            "status": "completed",
        }

    except Exception as exc:
        logger.exception("ingestion_failed", document_id=document_id)
        _update_status(document_id, "failed", error_message=str(exc)[:500])

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))

        return {
            "document_id": document_id,
            "status": "failed",
            "error": str(exc)[:500],
        }


@celery.task(bind=True, name="app.ingestion.tasks.reindex_user_documents")
def reindex_user_documents(self, user_id: int) -> dict:
    """Re-ingest all documents for a user by deleting vectors and re-processing."""
    logger.info("reindex_started", user_id=user_id)

    async def _get_user_documents():
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import select

        from app.database.models import Document

        engine = _get_task_engine()
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            result = await session.execute(
                select(Document).where(
                    Document.user_id == user_id,
                    Document.status.in_(["completed", "failed"]),
                )
            )
            docs = result.scalars().all()
            data = [(d.id, d.filename) for d in docs]
        return data

    try:
        documents = _run_sync_db(_get_user_documents())
        settings = get_settings()
        results = []

        # Wipe all user vectors first so deleted-doc orphans cannot linger
        from app.vectorstore.collections import delete_user_vectors
        try:
            delete_user_vectors(user_id)
        except Exception:
            logger.warning("reindex_delete_user_vectors_failed", user_id=user_id)

        for doc_id, filename in documents:
            file_path = str(settings.UPLOAD_DIR + "/" + filename)
            ingest_document.delay(doc_id, file_path, user_id)
            results.append(doc_id)

        logger.info("reindex_queued", user_id=user_id, document_count=len(results))
        return {
            "user_id": user_id,
            "documents_queued": len(results),
            "document_ids": results,
        }

    except Exception as exc:
        logger.exception("reindex_failed", user_id=user_id)
        return {"user_id": user_id, "status": "failed", "error": str(exc)[:500]}
