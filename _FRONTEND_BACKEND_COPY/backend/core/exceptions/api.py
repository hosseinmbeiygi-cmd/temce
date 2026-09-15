from __future__ import annotations

from typing import Any

from core.exceptions import AppError


class APIError(AppError):
    def __init__(
        self,
        message: str = "API error",
        code: str = "API_ERROR",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        super().__init__(message=message, code=code, details=details)


class BadRequestError(APIError):
    def __init__(self, message: str = "Bad request", details: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code="BAD_REQUEST", status_code=400, details=details)


class NotFoundError(APIError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message=message, code="NOT_FOUND", status_code=404)


class ConflictError(APIError):
    def __init__(self, message: str = "Resource conflict") -> None:
        super().__init__(message=message, code="CONFLICT", status_code=409)


class UnprocessableEntityError(APIError):
    def __init__(self, message: str = "Unprocessable entity", details: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code="UNPROCESSABLE", status_code=422, details=details)


class InternalServerError(APIError):
    def __init__(self, message: str = "Internal server error") -> None:
        super().__init__(message=message, code="INTERNAL_ERROR", status_code=500)


class ServiceUnavailableError(APIError):
    def __init__(self, message: str = "Service unavailable") -> None:
        super().__init__(message=message, code="SERVICE_UNAVAILABLE", status_code=503)
