"""Chat service – conversation management. RAG integration added in Phase 4."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.database.models import Conversation, Message
from app.database.repositories.conversation_repo import ConversationRepository

logger = get_logger(__name__)


class ChatService:

    def __init__(self, db: AsyncSession) -> None:
        self._repo = ConversationRepository(db)

    async def create_conversation(
        self,
        user_id: int,
        title: str | None = None,
    ) -> Conversation:
        conversation = await self._repo.create(user_id, title=title)
        logger.info(
            "created_conversation",
            conversation_id=conversation.id,
            user_id=user_id,
        )
        return conversation

    async def list_conversations(
        self,
        user_id: int,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Conversation]:
        return await self._repo.list_by_user(user_id, limit=limit, offset=offset)

    async def get_conversation(
        self,
        conversation_id: str,
        user_id: int,
    ) -> Conversation:
        conversation = await self._repo.get_by_id(conversation_id, user_id)
        if conversation is None:
            raise NotFoundError("Conversation")
        return conversation

    async def add_message(
        self,
        conversation_id: str,
        user_id: int,
        role: str,
        content: str,
        citations: str | None = None,
    ) -> Message:
        conversation = await self._repo.get_by_id(conversation_id, user_id)
        if conversation is None:
            raise NotFoundError("Conversation")

        message = await self._repo.add_message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            citations=citations,
        )
        logger.info(
            "added_message",
            conversation_id=conversation_id,
            message_id=message.id,
            role=role,
        )
        return message

    async def get_messages(
        self,
        conversation_id: str,
        user_id: int,
        *,
        limit: int = 50,
    ) -> list[Message]:
        conversation = await self._repo.get_by_id(conversation_id, user_id)
        if conversation is None:
            raise NotFoundError("Conversation")

        return await self._repo.get_messages(conversation_id, limit=limit)

    async def delete_conversation(
        self,
        conversation_id: str,
        user_id: int,
    ) -> None:
        deleted = await self._repo.delete(conversation_id, user_id)
        if not deleted:
            raise NotFoundError("Conversation")
        logger.info(
            "deleted_conversation",
            conversation_id=conversation_id,
            user_id=user_id,
        )

    async def delete_all_conversations(self, user_id: int) -> int:
        count = await self._repo.delete_all_by_user(user_id)
        logger.info("deleted_all_conversations", user_id=user_id, count=count)
        return count
