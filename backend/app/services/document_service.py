"""Document service – upload, delete, list operations."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.database.models import Document
from app.database.repositories.document_repo import DocumentRepository

logger = get_logger(__name__)


class DocumentService:

    def __init__(self, db: AsyncSession) -> None:
        self._repo = DocumentRepository(db)

    async def list_documents(
        self,
        user_id: int,
        *,
        status: str | None = None,
        content_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Document], int]:
        documents = await self._repo.list_by_user(
            user_id,
            status=status,
            content_type=content_type,
            limit=limit,
            offset=offset,
        )
        total = await self._repo.count_by_user(user_id)
        logger.info(
            "listed_documents",
            user_id=user_id,
            count=len(documents),
            total=total,
        )
        return documents, total

    async def get_document(self, document_id: str, user_id: int) -> Document:
        document = await self._repo.get_by_id(document_id, user_id)
        if document is None:
            raise NotFoundError("Document")
        return document

    async def delete_document(self, document_id: str, user_id: int) -> None:
        document = await self._repo.get_by_id(document_id, user_id)
        if document is None:
            raise NotFoundError("Document")

        from app.vectorstore.collections import delete_document_vectors

        delete_document_vectors(document_id, user_id)

        settings = get_settings()
        file_path = Path(settings.UPLOAD_DIR) / document.filename
        if file_path.exists():
            file_path.unlink()
            logger.info(
                "deleted_file",
                document_id=document_id,
                path=str(file_path),
            )

        await self._repo.delete(document_id, user_id)
        logger.info(
            "deleted_document",
            document_id=document_id,
            user_id=user_id,
        )
