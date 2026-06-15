from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base exception for all application errors."""

    def __init__(
        self, message: str = "An error occurred", code: str = "UNKNOWN", details: dict[str, Any] | None = None
    ) -> None:
        self.code = code
        self.details = details or {}
        super().__init__(message)


class DomainError(AppError):
    """Violation of a domain rule."""

    def __init__(
        self, message: str = "Domain rule violated", code: str = "DOMAIN_ERROR", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message=message, code=code, details=details)


class NotFoundError(DomainError):
    """Entity not found."""

    def __init__(self, entity: str = "Entity", identifier: str | None = None) -> None:
        msg = f"{entity} not found" + (f": {identifier}" if identifier else "")
        super().__init__(message=msg, code="NOT_FOUND", details={"entity": entity, "identifier": identifier})


class ValidationError(DomainError):
    """Input validation failure."""

    def __init__(self, message: str = "Validation failed", errors: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message=message, code="VALIDATION_ERROR", details={"errors": errors or []})


class ConfigurationError(AppError):
    """System configuration error."""

    def __init__(self, message: str = "Configuration error", key: str | None = None) -> None:
        super().__init__(message=message, code="CONFIG_ERROR", details={"key": key})


class InfrastructureError(AppError):
    """Infrastructure-level failure."""

    def __init__(self, message: str = "Infrastructure error", cause: Exception | None = None) -> None:
        super().__init__(message=message, code="INFRA_ERROR")
        self.__cause__ = cause


class ExternalServiceError(AppError):
    """External service/provider failure."""

    def __init__(
        self, service: str = "external", message: str = "External service error", status_code: int | None = None
    ) -> None:
        super().__init__(
            message=message, code=f"{service.upper()}_ERROR", details={"service": service, "status_code": status_code}
        )


class AuthenticationError(AppError):
    """Authentication failure."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message=message, code="AUTH_ERROR")


class AuthorizationError(AppError):
    """Authorization failure."""

    def __init__(self, message: str = "Permission denied") -> None:
        super().__init__(message=message, code="FORBIDDEN")


class RateLimitError(AppError):
    """Rate limit exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int | None = None) -> None:
        super().__init__(message=message, code="RATE_LIMIT", details={"retry_after": retry_after})
