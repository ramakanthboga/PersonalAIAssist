"""Shared test fixtures."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.models import Base
from app.database.session import get_db
from app.main import app
from app.security.email_validation import normalize_email

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine_test = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_test = async_sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def relax_registration_email_validation(monkeypatch):
    """Allow placeholder domains in tests (production still enforces real inboxes)."""
    monkeypatch.setattr(
        "app.services.user_service.validate_registration_email",
        normalize_email,
    )


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Use a fresh in-memory limiter in tests (ignore shared Redis counters)."""
    from app.security.rate_limiter import auth_rate_limiter, rate_limiter

    for limiter in (rate_limiter, auth_rate_limiter):
        limiter._memory.clear()
        # Prevent reconnecting to a shared Redis instance during the suite.
        limiter._redis = None
        limiter._redis_checked = True
    yield
    for limiter in (rate_limiter, auth_rate_limiter):
        limiter._memory.clear()
        limiter._redis = None
        limiter._redis_checked = True


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_test() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
