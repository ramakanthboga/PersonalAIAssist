"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.middleware import ErrorHandlerMiddleware, RequestIdMiddleware, TimingMiddleware
from app.api.routes import auth, chat, documents, health
from app.auth.oauth import configure_oauth
from app.core.config import get_settings
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()

    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    db_path = settings.DATABASE_URL.split("///")[-1]
    if db_path and db_path != settings.DATABASE_URL:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    configure_oauth()

    try:
        from app.vectorstore.collections import ensure_collection
        ensure_collection()
    except Exception:
        pass

    yield

    from app.vectorstore.qdrant_client import close_qdrant_client
    close_qdrant_client()

    from app.llm.langfuse_tracer import flush_langfuse
    flush_langfuse()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    app.add_middleware(TimingMiddleware)
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(RequestIdMiddleware)
    # Required for Authlib OAuth state (Google sign-in CSRF protection)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SECRET_KEY,
        same_site="lax",
        https_only=settings.is_production,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix=settings.API_V1_PREFIX, tags=["health"])
    app.include_router(auth.router, prefix=settings.API_V1_PREFIX, tags=["auth"])
    app.include_router(chat.router, prefix=settings.API_V1_PREFIX, tags=["chat"])
    app.include_router(documents.router, prefix=settings.API_V1_PREFIX, tags=["documents"])

    return app


app = create_app()
