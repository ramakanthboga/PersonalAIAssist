"""Celery application instance."""

from celery import Celery
from celery.signals import worker_process_init

from app.core.config import get_settings

settings = get_settings()

celery = Celery(
    "personalaiassist",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery.autodiscover_tasks(["app.ingestion"])


@worker_process_init.connect
def _warmup_worker_process(**kwargs) -> None:  # noqa: ARG001
    """Preload embedding model so the first ingest is not cold-start delayed."""
    try:
        from app.ingestion.embeddings import warmup_embedder
        from app.vectorstore.collections import ensure_collection

        warmup_embedder()
        ensure_collection()
    except Exception:
        # Warmup is best-effort; ingest will load on demand if this fails.
        from app.core.logging import get_logger

        get_logger(__name__).exception("celery_worker_warmup_failed")
