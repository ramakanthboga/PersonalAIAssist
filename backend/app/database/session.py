"""Async SQLAlchemy engine and session factory."""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_settings = get_settings()

_engine_kwargs: dict = {
    "echo": _settings.DEBUG,
    "future": True,
}

if _settings.DATABASE_URL.startswith("sqlite"):
    # Docker volume + SQLite: avoid pooled connections holding locks across requests,
    # and wait when another connection has the file momentarily.
    _engine_kwargs["connect_args"] = {"timeout": 60}
    _engine_kwargs["poolclass"] = NullPool

engine = create_async_engine(_settings.DATABASE_URL, **_engine_kwargs)


if _settings.DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=60000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency – yields an async session and ensures cleanup."""
    import asyncio

    from sqlalchemy.exc import OperationalError

    async with async_session_factory() as session:
        try:
            yield session
            # Retry commit if SQLite briefly reports "database is locked".
            for attempt in range(5):
                try:
                    await session.commit()
                    break
                except OperationalError as exc:
                    if "database is locked" not in str(exc).lower() or attempt == 4:
                        raise
                    await session.rollback()
                    await asyncio.sleep(0.2 * (attempt + 1))
        except Exception:
            await session.rollback()
            raise
