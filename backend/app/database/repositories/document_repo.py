"""Document repository (data-access layer)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Document


class DocumentRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, document_id: str, user_id: int) -> Document | None:
        stmt = select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: int,
        *,
        status: str | None = None,
        content_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Document]:
        stmt = select(Document).where(Document.user_id == user_id)

        if status is not None:
            stmt = stmt.where(Document.status == status)
        if content_type is not None:
            stmt = stmt.where(Document.content_type == content_type)

        stmt = stmt.order_by(Document.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        user_id: int,
        filename: str,
        original_filename: str,
        content_type: str,
        file_size: int,
    ) -> Document:
        document = Document(
            user_id=user_id,
            filename=filename,
            original_filename=original_filename,
            content_type=content_type,
            file_size=file_size,
        )
        self._session.add(document)
        await self._session.flush()
        return document

    async def update_status(
        self,
        document_id: str,
        status: str,
        *,
        chunk_count: int | None = None,
        error_message: str | None = None,
    ) -> Document | None:
        stmt = select(Document).where(Document.id == document_id)
        result = await self._session.execute(stmt)
        document = result.scalar_one_or_none()
        if document is None:
            return None

        document.status = status
        if chunk_count is not None:
            document.chunk_count = chunk_count
        if error_message is not None:
            document.error_message = error_message

        await self._session.flush()
        return document

    async def delete(self, document_id: str, user_id: int) -> bool:
        document = await self.get_by_id(document_id, user_id)
        if document is None:
            return False
        await self._session.delete(document)
        await self._session.flush()
        return True

    async def count_by_user(self, user_id: int) -> int:
        stmt = select(func.count()).select_from(Document).where(
            Document.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def count_completed_by_user(self, user_id: int) -> int:
        stmt = select(func.count()).select_from(Document).where(
            Document.user_id == user_id,
            Document.status == "completed",
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def list_completed_ids_by_user(self, user_id: int) -> list[str]:
        """Return IDs of completed documents owned by the user (for RAG allow-list)."""
        stmt = select(Document.id).where(
            Document.user_id == user_id,
            Document.status == "completed",
        )
        result = await self._session.execute(stmt)
        return [str(row[0]) for row in result.all()]

    async def delete_all_by_user(self, user_id: int) -> list[Document]:
        """Delete all document rows for a user. Returns the deleted documents (pre-delete)."""
        documents = await self.list_by_user(user_id, limit=10_000, offset=0)
        for document in documents:
            await self._session.delete(document)
        await self._session.flush()
        return documents
