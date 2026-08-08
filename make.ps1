# Windows-friendly wrapper for Makefile targets.
# Usage: .\make.ps1 infra
#        .\make.ps1 up
#        .\make.ps1 help

param(
    [Parameter(Position = 0)]
    [string]$Target = "help",

    [string]$MSG = ""
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

function Test-DockerDaemon {
    # Prefer a direct call (Start-Job can miss PATH and fails on newer "Server: Docker Desktop ..." output).
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = & docker info --format "{{.ServerVersion}}" 2>&1 | Out-String
    $ok = ($LASTEXITCODE -eq 0 -and $output -match "\d+\.\d+")
    $ErrorActionPreference = $prev

    if ($ok) { return $true }

    Write-Host "Docker Desktop is not running or is unhealthy." -ForegroundColor Red
    if ($output -match "500 Internal Server Error") {
        Write-Host ""
        Write-Host "Docker returned HTTP 500 (engine crashed or is still starting)." -ForegroundColor Yellow
        Write-Host "This often happens after a failed large backend build." -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "1. Quit Docker Desktop completely (tray icon -> Quit)" -ForegroundColor Yellow
    Write-Host "2. Start Docker Desktop again and wait until it shows Running" -ForegroundColor Yellow
    Write-Host "3. Optional: docker system prune -f  (frees disk from failed builds)" -ForegroundColor Yellow
    Write-Host "4. Retry: .\make.ps1 start" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To skip the heavy ML image build, use local backend instead:" -ForegroundColor Cyan
    Write-Host "  .\make.ps1 infra" -ForegroundColor Cyan
    Write-Host "  .\make.ps1 backend" -ForegroundColor Cyan
    return $false
}

function Show-Help {
    Write-Host ""
    Write-Host "Available commands:" -ForegroundColor Cyan
    Write-Host "  up              Build images and start all services"
    Write-Host "  start           Start services without rebuilding"
    Write-Host "  down            Stop all services"
    Write-Host "  logs            Tail logs for all services"
    Write-Host "  infra           Start only Qdrant + Redis (for local dev)"
    Write-Host "  backend         Run backend dev server locally"
    Write-Host "  frontend        Run frontend dev server locally"
    Write-Host "  worker          Run Celery worker locally"
    Write-Host "  cursor-proxy    Host proxy so Docker can use your Cursor API key"
    Write-Host "  migrate         Run Alembic migrations"
    Write-Host "  migrate-create  Create a new migration (use -MSG 'description')"
    Write-Host "  test            Run backend tests"
    Write-Host "  test-cov        Run tests with coverage report"
    Write-Host "  lint            Run linting"
    Write-Host "  format          Auto-format code"
    Write-Host "  clean           Remove caches, build artifacts, and volumes"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\make.ps1 infra"
    Write-Host "  .\make.ps1 migrate-create -MSG `"add users table`""
    Write-Host ""
}

function Get-DotEnvValue {
    param(
        [string]$Name,
        [string]$EnvPath
    )
    if (-not (Test-Path $EnvPath)) { return $null }
    foreach ($line in Get-Content $EnvPath) {
        if ($line -match '^\s*#') { continue }
        if ($line -match "^\s*$([regex]::Escape($Name))=(.*)$") {
            return $matches[1].Trim()
        }
    }
    return $null
}

Push-Location $Root
try {
    switch ($Target.ToLower()) {
        "help" { Show-Help }
        "up" {
            if (-not (Test-DockerDaemon)) { exit 1 }
            # Build one service at a time – large ML images can crash Docker Desktop if built in parallel.
            Write-Host "Building backend image (CPU-only PyTorch, ~5-10 min first run)..." -ForegroundColor Cyan
            docker compose build backend
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            Write-Host "Building frontend image..." -ForegroundColor Cyan
            docker compose build frontend
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            Write-Host "Starting all services..." -ForegroundColor Cyan
            docker compose up -d
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            Write-Host "Done. Frontend: http://localhost:3000  API: http://localhost:8000/docs" -ForegroundColor Green
        }
        "start" {
            if (-not (Test-DockerDaemon)) { exit 1 }
            Write-Host "Starting services (no rebuild)..." -ForegroundColor Cyan
            docker compose up -d
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            Write-Host "Done. Frontend: http://localhost:3000  API: http://localhost:8000/docs" -ForegroundColor Green
        }
        "down" { docker compose down }
        "logs" { docker compose logs -f }
        "infra" { docker compose up -d qdrant redis }
        "backend" {
            Push-Location backend
            uvicorn app.main:app --reload --port 8000
        }
        "frontend" {
            Push-Location frontend
            npm run dev
        }
        "worker" {
            Push-Location backend
            celery -A celery_app.celery worker --loglevel=info
        }
        "cursor-proxy" {
            $envPath = Join-Path $Root ".env"
            $key = Get-DotEnvValue -Name "CURSOR_API_KEY" -EnvPath $envPath
            if (-not $key) {
                Write-Error "CURSOR_API_KEY not found in .env"
            }
            $py = Join-Path $Root ".venv\Scripts\python.exe"
            if (-not (Test-Path $py)) {
                Write-Error "Project venv not found at .venv. Create it and pip install -r backend/requirements.txt"
            }
            $env:CURSOR_API_KEY = $key
            $env:PORT = "8080"
            $env:HOST = "0.0.0.0"
            $env:CURSOR_CWD = $Root
            $env:DEFAULT_MODEL = (Get-DotEnvValue -Name "LLM_MODEL" -EnvPath $envPath)
            if (-not $env:DEFAULT_MODEL) { $env:DEFAULT_MODEL = "composer-2.5" }
            Write-Host "Starting Cursor OpenAI proxy on http://localhost:8080" -ForegroundColor Cyan
            Write-Host "Requires Cursor IDE running on this machine." -ForegroundColor Yellow
            Write-Host "In .env set: CURSOR_PROXY_URL=http://host.docker.internal:8080/v1" -ForegroundColor Yellow
            Write-Host "Keep this window open while chatting via Docker." -ForegroundColor Yellow
            & $py (Join-Path $Root "tools\cursor_proxy.py")
        }
        "migrate" {
            Push-Location backend
            alembic upgrade head
        }
        "migrate-create" {
            if (-not $MSG) {
                Write-Error "Usage: .\make.ps1 migrate-create -MSG `"your message`""
            }
            Push-Location backend
            alembic revision --autogenerate -m $MSG
        }
        "test" {
            Push-Location backend
            python -m pytest tests/ -v --tb=short
        }
        "test-cov" {
            Push-Location backend
            python -m pytest tests/ -v --cov=app --cov-report=term-missing
        }
        "lint" {
            Push-Location backend
            python -m ruff check app/ tests/
        }
        "format" {
            Push-Location backend
            python -m ruff format app/ tests/
        }
        "clean" {
            docker compose down -v
            Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
                Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
            Get-ChildItem -Path . -Recurse -Directory -Filter ".pytest_cache" -ErrorAction SilentlyContinue |
                Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
            Remove-Item -Path "backend/data/app.db" -Force -ErrorAction SilentlyContinue
        }
        default {
            Write-Error "Unknown target: $Target. Run .\make.ps1 help"
        }
    }
}
finally {
    Pop-Location
}
