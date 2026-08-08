"""User repository (data-access layer)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalars().first()

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.email == email)
        )
        return result.scalars().first()

    async def get_by_oauth_sub(self, provider: str, oauth_sub: str) -> User | None:
        result = await self._session.execute(
            select(User).where(
                User.oauth_provider == provider,
                User.oauth_sub == oauth_sub,
            )
        )
        return result.scalars().first()

    async def create(
        self,
        email: str,
        hashed_password: str | None = None,
        full_name: str | None = None,
        *,
        oauth_provider: str | None = None,
        oauth_sub: str | None = None,
    ) -> User:
        user = User(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            oauth_provider=oauth_provider,
            oauth_sub=oauth_sub,
        )
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def update(self, user: User, **kwargs: object) -> User:
        for key, value in kwargs.items():
            setattr(user, key, value)
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def deactivate(self, user: User) -> User:
        return await self.update(user, is_active=False)
