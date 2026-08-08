"""Custom FastAPI middleware (error handling, request ID, etc.)."""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.security.error_sanitize import public_detail_from_exc

logger = get_logger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except AppError as exc:
            # Never return stack traces / internal paths via AppError.message.
            logger.warning(
                "app_error",
                status=exc.status_code,
                message=exc.message,
                path=str(request.url.path),
            )
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": public_detail_from_exc(exc)},
            )
        except Exception:
            logger.exception("unhandled_error", path=str(request.url))
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )


class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"
        return response
