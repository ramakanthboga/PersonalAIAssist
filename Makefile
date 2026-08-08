.PHONY: help dev up down logs backend frontend worker migrate test lint clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Docker ───────────────────────────────────────────────────────────

up: ## Build images and start all services
	docker compose build backend
	docker compose build frontend
	docker compose up -d

start: ## Start services without rebuilding
	docker compose up -d

down: ## Stop all services
	docker compose down

logs: ## Tail logs for all services
	docker compose logs -f

infra: ## Start only Qdrant + Redis (for local dev)
	docker compose up -d qdrant redis

# ── Local Development ────────────────────────────────────────────────

backend: ## Run backend dev server locally
	cd backend && uvicorn app.main:app --reload --port 8000

frontend: ## Run frontend dev server locally
	cd frontend && npm run dev

worker: ## Run Celery worker locally
	cd backend && celery -A celery_app.celery worker --loglevel=info

# ── Database ─────────────────────────────────────────────────────────

migrate: ## Run Alembic migrations
	cd backend && alembic upgrade head

migrate-create: ## Create a new migration (usage: make migrate-create MSG="add users table")
	cd backend && alembic revision --autogenerate -m "$(MSG)"

# ── Testing ──────────────────────────────────────────────────────────

test: ## Run backend tests
	cd backend && python -m pytest tests/ -v --tb=short

test-cov: ## Run tests with coverage report
	cd backend && python -m pytest tests/ -v --cov=app --cov-report=term-missing

# ── Code Quality ─────────────────────────────────────────────────────

lint: ## Run linting
	cd backend && python -m ruff check app/ tests/

format: ## Auto-format code
	cd backend && python -m ruff format app/ tests/

# ── Cleanup ──────────────────────────────────────────────────────────

clean: ## Remove caches, build artifacts, and volumes
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/data/app.db
