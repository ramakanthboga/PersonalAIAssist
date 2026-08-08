"""Application-level exception hierarchy."""

from __future__ import annotations


class AppError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AuthenticationError(AppError):
    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, status_code=401)


class AuthorizationError(AppError):
    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message, status_code=403)


class NotFoundError(AppError):
    def __init__(self, resource: str = "Resource") -> None:
        super().__init__(f"{resource} not found", status_code=404)


class ValidationError(AppError):
    def __init__(self, message: str = "Validation failed") -> None:
        super().__init__(message, status_code=422)


class RateLimitError(AppError):
    def __init__(self, message: str = "Rate limit exceeded") -> None:
        super().__init__(message, status_code=429)


class LLMProviderError(AppError):
    def __init__(self, provider: str, message: str) -> None:
        super().__init__(f"[{provider}] {message}", status_code=502)


class DocumentIngestionError(AppError):
    def __init__(self, message: str = "Document ingestion failed") -> None:
        super().__init__(message, status_code=500)
