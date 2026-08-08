"""
Application configuration via Pydantic Settings.

All secrets and tunables are read from environment variables or a .env file.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from functools import lru_cache
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LLMProviderName(str, Enum):
    CURSOR = "cursor"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"


_BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
_ROOT_DIR = _BASE_DIR.parent


def _env_files() -> tuple[str, ...]:
    """Load root .env first, then backend/.env (backend overrides root)."""
    files: list[Path] = [_ROOT_DIR / ".env", _BASE_DIR / ".env"]
    return tuple(str(path) for path in files if path.is_file())


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_files(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── General ──────────────────────────────────────────────────────────
    APP_NAME: str = "PersonalAIAssist"
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    ALLOWED_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    # ── Auth / JWT ───────────────────────────────────────────────────────
    SECRET_KEY: str = Field(
        ..., description="HMAC secret for JWT signing – generate with `openssl rand -hex 32`"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8h – long RAG/Cursor replies outlast 15m tokens
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # ── Google OAuth (sign-in) — separate from GOOGLE_API_KEY (Gemini) ──
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    # Public API origin used to build the Google redirect URI
    # e.g. http://localhost:8000  →  {base}/api/v1/auth/google/callback
    OAUTH_REDIRECT_BASE_URL: str = "http://localhost:8000"
    # Frontend page that stores JWTs after Google callback
    FRONTEND_OAUTH_SUCCESS_URL: str = "http://localhost:3000/auth/callback"

    @field_validator(
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "OAUTH_REDIRECT_BASE_URL",
        "FRONTEND_OAUTH_SUCCESS_URL",
        mode="before",
    )
    @classmethod
    def strip_oauth_strings(cls, v: Any) -> Any:
        if isinstance(v, str):
            cleaned = v.strip().strip('"').strip("'")
            return cleaned or None
        return v

    # ── Database ─────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default=f"sqlite+aiosqlite:///{_BASE_DIR / 'data' / 'app.db'}",
        description="SQLAlchemy async connection string",
    )

    # ── Redis ────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Qdrant ───────────────────────────────────────────────────────────
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_GRPC_PORT: int = 6334
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION: str = "documents"

    # ── LLM Providers ────────────────────────────────────────────────────
    LLM_PROVIDER: LLMProviderName = LLMProviderName.OPENAI
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 2048

    CURSOR_API_KEY: str | None = None
    # Cloud agent repo when running in Docker (Cursor local agents need the host IDE).
    # Example: https://github.com/owner/repo
    CURSOR_CLOUD_REPO: str | None = None
    # Host proxy for Cursor in Docker (legacy; cloud mode preferred).
    CURSOR_PROXY_URL: str | None = None
    CURSOR_PROXY_AUTH_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    GOOGLE_API_KEY: str | None = None
    OPENROUTER_API_KEY: str | None = None

    # ── Embeddings ───────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "nomic-ai/nomic-embed-text-v1.5"
    EMBEDDING_DIMENSION: int = 768
    EMBEDDING_BATCH_SIZE: int = 64

    # ── Reranker ─────────────────────────────────────────────────────────
    COHERE_API_KEY: str | None = None
    RERANKER_MODEL: str = "rerank-english-v3.0"
    RERANKER_TOP_K: int = 5

    # ── RAG ──────────────────────────────────────────────────────────────
    # Larger chunks → fewer embeddings per document (faster ingest).
    CHUNK_SIZE: int = 1024
    CHUNK_OVERLAP: int = 128
    RETRIEVAL_TOP_K: int = 10
    # Drop weak matches so unrelated / stale chunks are not treated as context.
    # Cosine similarity (dense) and Cohere relevance scores are both ~0–1.
    MIN_RETRIEVAL_SCORE: float = 0.32
    MIN_RERANK_SCORE: float = 0.20
    # Broader context for "summarize the document" style questions.
    SYNTHESIS_RETRIEVAL_TOP_K: int = 30
    SYNTHESIS_CONTEXT_CHUNKS: int = 24

    # ── File Uploads ─────────────────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 50
    UPLOAD_DIR: str = str(_BASE_DIR / "data" / "uploads")
    # Keep in sync with frontend UploadZone + ingestion parser extractors.
    # Legacy .doc/.xls are intentionally omitted: extractors only support OOXML
    # (.docx via python-docx, .xlsx via openpyxl).
    ALLOWED_EXTENSIONS: Annotated[list[str], NoDecode] = [
        ".pdf", ".docx", ".txt", ".md", ".csv", ".xlsx",
        ".png", ".jpg", ".jpeg", ".tif", ".tiff",
    ]

    # ── Celery ───────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Observability ────────────────────────────────────────────────────
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    LOG_LEVEL: str = "INFO"

    # ── Rate Limiting ────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 30

    # ── Validators ───────────────────────────────────────────────────────
    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("ALLOWED_EXTENSIONS", mode="before")
    @classmethod
    def parse_extensions(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [ext.strip() for ext in v.split(",")]
        return v

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == Environment.PRODUCTION


@lru_cache
def get_settings() -> Settings:
    """Singleton settings instance, cached for the process lifetime."""
    return Settings()
