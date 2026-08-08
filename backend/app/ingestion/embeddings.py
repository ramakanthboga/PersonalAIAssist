"""Embedding generation using sentence-transformers (Nomic) or OpenAI."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Shorthand aliases → Hugging Face repo ids
_EMBEDDING_MODEL_ALIASES: dict[str, str] = {
    "nomic-embed-text-v1.5": "nomic-ai/nomic-embed-text-v1.5",
}


def _resolve_embedding_model(name: str) -> str:
    return _EMBEDDING_MODEL_ALIASES.get(name, name)


class EmbeddingProvider(ABC):
    """Abstract embedding provider."""

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...

    @abstractmethod
    def embed_query(self, query: str) -> list[float]:
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        ...


class NomicEmbedder(EmbeddingProvider):
    """Local embeddings via sentence-transformers using Nomic Embed v1.5."""

    def __init__(self, model_name: str | None = None) -> None:
        from sentence_transformers import SentenceTransformer

        settings = get_settings()
        self._model_name = _resolve_embedding_model(model_name or settings.EMBEDDING_MODEL)
        self._batch_size = max(1, settings.EMBEDDING_BATCH_SIZE)
        self._model = SentenceTransformer(self._model_name, trust_remote_code=True)
        self._dimension = settings.EMBEDDING_DIMENSION
        logger.info(
            "loaded_embedding_model",
            model=self._model_name,
            batch_size=self._batch_size,
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        prefixed = [f"search_document: {t}" for t in texts]
        embeddings = self._model.encode(
            prefixed,
            batch_size=self._batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        prefixed = f"search_query: {query}"
        embedding = self._model.encode(
            [prefixed],
            batch_size=1,
            show_progress_bar=False,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return embedding[0].tolist()

    @property
    def dimension(self) -> int:
        return self._dimension


class OpenAIEmbedder(EmbeddingProvider):
    """OpenAI embeddings via the openai SDK."""

    def __init__(self, model_name: str = "text-embedding-3-small") -> None:
        import openai

        settings = get_settings()
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required for OpenAI embeddings")
        self._client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self._model_name = model_name
        self._dimension = 1536
        self._batch_size = max(1, settings.EMBEDDING_BATCH_SIZE)
        logger.info("loaded_openai_embedder", model=self._model_name)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # OpenAI caps ~2048 inputs per request; respect configured batch size.
        batch_size = min(self._batch_size, 2048)
        all_vectors: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = self._client.embeddings.create(input=batch, model=self._model_name)
            # API may return out of order — sort by index.
            ordered = sorted(response.data, key=lambda item: item.index)
            all_vectors.extend(item.embedding for item in ordered)
        return all_vectors

    def embed_query(self, query: str) -> list[float]:
        return self.embed_texts([query])[0]

    @property
    def dimension(self) -> int:
        return self._dimension


_embedder: EmbeddingProvider | None = None


def get_embedder() -> EmbeddingProvider:
    """Return the singleton embedding provider based on settings."""
    global _embedder
    if _embedder is None:
        settings = get_settings()
        model = _resolve_embedding_model(settings.EMBEDDING_MODEL)
        if "openai" in model.lower() or "ada" in model.lower():
            _embedder = OpenAIEmbedder(model_name=model)
        else:
            _embedder = NomicEmbedder(model_name=model)
    return _embedder


def warmup_embedder() -> None:
    """Load the embedding model at worker start to avoid first-request latency."""
    get_embedder()
