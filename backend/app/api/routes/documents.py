"""Document routes – upload, list, get, delete, and reindex."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_rate_limited_user
from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.models import User
from app.database.repositories.document_repo import DocumentRepository
from app.database.session import get_db
from app.security.file_validator import (
    FileValidationError,
    content_type_for_extension,
    validate_upload,
)

logger = get_logger(__name__)


class DocumentResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    content_type: str
    file_size: int
    status: str
    chunk_count: int
    created_at: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


def _document_to_response(doc) -> DocumentResponse:
    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        original_filename=doc.original_filename,
        content_type=doc.content_type,
        file_size=doc.file_size,
        status=doc.status,
        chunk_count=doc.chunk_count,
        created_at=doc.created_at.isoformat(),
    )


router = APIRouter(prefix="/documents")

_UPLOAD_READ_CHUNK = 1024 * 1024  # 1 MiB


async def _read_upload_capped(file: UploadFile, max_bytes: int) -> bytes:
    """Read upload in chunks and abort early if it exceeds the size cap."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_UPLOAD_READ_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum size of {max_bytes // (1024 * 1024)} MB",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_rate_limited_user),
):
    settings = get_settings()

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided",
        )

    content = await _read_upload_capped(file, settings.max_upload_bytes)
    try:
        original_filename = validate_upload(file.filename, content)
    except FileValidationError as exc:
        status_code = (
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            if "exceeds maximum" in exc.message
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=exc.message) from exc

    ext = Path(original_filename).suffix.lower()
    stored_filename = f"{uuid.uuid4().hex}{ext}"
    content_type = content_type_for_extension(ext)

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / stored_filename

    file_path.write_bytes(content)

    repo = DocumentRepository(db)
    document = await repo.create(
        user_id=current_user.id,
        filename=stored_filename,
        original_filename=original_filename,
        content_type=content_type,
        file_size=len(content),
    )

    from app.ingestion.tasks import ingest_document
    ingest_document.delay(document.id, str(file_path), current_user.id)

    return _document_to_response(document)


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    status_filter: str | None = Query(None, alias="status"),
    content_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_rate_limited_user),
):
    repo = DocumentRepository(db)
    documents = await repo.list_by_user(
        user_id=current_user.id,
        status=status_filter,
        content_type=content_type,
        limit=limit,
        offset=offset,
    )
    total = await repo.count_by_user(current_user.id)

    return DocumentListResponse(
        documents=[_document_to_response(doc) for doc in documents],
        total=total,
    )


class ClearAllResponse(BaseModel):
    deleted_documents: int
    deleted_conversations: int


@router.delete("/clear", response_model=ClearAllResponse)
async def clear_all_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_rate_limited_user),
):
    """Remove all of the user's documents, vectors, uploaded files, and chat history.

    Use this for a full reset so RAG cannot answer from previously indexed content.
    """
    settings = get_settings()
    repo = DocumentRepository(db)

    # Wipe search index first so no stale chunks remain for this user.
    try:
        from app.vectorstore.collections import delete_user_vectors
        delete_user_vectors(current_user.id)
    except Exception as exc:
        logger.error(
            "failed_to_clear_user_vectors",
            user_id=current_user.id,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to clear search index. Please try again.",
        ) from exc

    documents = await repo.list_by_user(current_user.id, limit=10_000, offset=0)
    for document in documents:
        file_path = Path(settings.UPLOAD_DIR) / document.filename
        if file_path.exists():
            try:
                file_path.unlink()
            except OSError as exc:
                logger.warning(
                    "failed_to_unlink_upload",
                    document_id=document.id,
                    path=str(file_path),
                    error=str(exc),
                )

    deleted_docs = await repo.delete_all_by_user(current_user.id)

    from app.services.chat_service import ChatService
    chat_svc = ChatService(db)
    deleted_conversations = await chat_svc.delete_all_conversations(current_user.id)

    logger.info(
        "cleared_all_user_data",
        user_id=current_user.id,
        deleted_documents=len(deleted_docs),
        deleted_conversations=deleted_conversations,
    )
    return ClearAllResponse(
        deleted_documents=len(deleted_docs),
        deleted_conversations=deleted_conversations,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_rate_limited_user),
):
    repo = DocumentRepository(db)
    document = await repo.get_by_id(document_id, user_id=current_user.id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return _document_to_response(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_rate_limited_user),
):
    settings = get_settings()
    repo = DocumentRepository(db)

    document = await repo.get_by_id(document_id, user_id=current_user.id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Remove from search index first so RAG cannot keep using orphan chunks.
    try:
        from app.vectorstore.collections import delete_document_vectors
        delete_document_vectors(document_id, current_user.id)
    except Exception as exc:
        logger.error(
            "failed_to_delete_document_vectors",
            document_id=document_id,
            user_id=current_user.id,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to remove document from search index. Please try again.",
        ) from exc

    file_path = Path(settings.UPLOAD_DIR) / document.filename
    if file_path.exists():
        file_path.unlink()

    await repo.delete(document_id, user_id=current_user.id)


@router.post("/reindex")
async def reindex_documents(current_user: User = Depends(get_rate_limited_user)):
    from app.ingestion.tasks import reindex_user_documents
    task = reindex_user_documents.delay(current_user.id)
    return {"status": "queued", "task_id": task.id}


@router.get("/status/{document_id}")
async def get_ingestion_status(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_rate_limited_user),
):
    """Get the ingestion status and progress of a document."""
    repo = DocumentRepository(db)
    document = await repo.get_by_id(document_id, user_id=current_user.id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return {
        "id": document.id,
        "status": document.status,
        "chunk_count": document.chunk_count,
        "error_message": document.error_message,
    }
