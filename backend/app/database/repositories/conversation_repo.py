"""Conversation / message repository (data-access layer)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Conversation, Message


class ConversationRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self, conversation_id: str, user_id: int
    ) -> Conversation | None:
        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: int,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self, user_id: int, title: str | None = None
    ) -> Conversation:
        conversation = Conversation(user_id=user_id, title=title)
        self._session.add(conversation)
        await self._session.flush()
        return conversation

    async def delete(self, conversation_id: str, user_id: int) -> bool:
        conversation = await self.get_by_id(conversation_id, user_id)
        if conversation is None:
            return False
        await self._session.delete(conversation)
        await self._session.flush()
        return True

    async def delete_all_by_user(self, user_id: int) -> int:
        """Delete all conversations (and cascaded messages) for a user."""
        conversations = await self.list_by_user(user_id, limit=10_000, offset=0)
        count = len(conversations)
        for conversation in conversations:
            await self._session.delete(conversation)
        await self._session.flush()
        return count

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        citations: str | None = None,
        token_count: int | None = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            citations=citations,
            token_count=token_count,
        )
        self._session.add(message)
        await self._session.flush()
        return message

    async def get_messages(
        self, conversation_id: str, *, limit: int = 50
    ) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
