# ── Builder stage ──────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements-docker.txt .
# Use PyTorch CPU wheel index as primary so sentence-transformers never pulls NVIDIA CUDA wheels.
RUN pip install --no-cache-dir --prefix=/install \
    --index-url https://download.pytorch.org/whl/cpu \
    --extra-index-url https://pypi.org/simple \
    -r requirements-docker.txt

# ── Runtime stage ──────────────────────────────────────────────────
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/data/hf-cache \
    TRANSFORMERS_CACHE=/app/data/hf-cache \
    SENTENCE_TRANSFORMERS_HOME=/app/data/hf-cache

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl tesseract-ocr && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd -r appuser && useradd -r -g appuser appuser

COPY --from=builder /install /usr/local

COPY . .

RUN sed -i 's/\r$//' docker-entrypoint.sh && \
    chmod +x docker-entrypoint.sh && \
    mkdir -p data/uploads data/hf-cache && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["/bin/sh", "./docker-entrypoint.sh"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
