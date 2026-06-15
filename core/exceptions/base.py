from __future__ import annotations

from typing import Any


class AppError(Exception):
    def __init__(
        self, message: str = "An error occurred", code: str = "UNKNOWN", details: dict[str, Any] | None = None
    ) -> None:
        self.code = code
        self.details = details or {}
        super().__init__(message)


class DomainError(AppError):
    def __init__(
        self, message: str = "Domain rule violated", code: str = "DOMAIN_ERROR", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message=message, code=code, details=details)


class NotFoundError(DomainError):
    def __init__(self, entity: str = "Entity", identifier: str | None = None) -> None:
        msg = f"{entity} not found" + (f": {identifier}" if identifier else "")
        super().__init__(message=msg, code="NOT_FOUND", details={"entity": entity, "identifier": identifier})


class ValidationError(DomainError):
    def __init__(self, message: str = "Validation failed", errors: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message=message, code="VALIDATION_ERROR", details={"errors": errors or []})


class ConfigurationError(AppError):
    def __init__(self, message: str = "Configuration error", key: str | None = None) -> None:
        super().__init__(message=message, code="CONFIG_ERROR", details={"key": key})


class InfrastructureError(AppError):
    def __init__(self, message: str = "Infrastructure error", cause: Exception | None = None) -> None:
        super().__init__(message=message, code="INFRA_ERROR")
        self.__cause__ = cause


class ExternalServiceError(AppError):
    def __init__(
        self, service: str = "external", message: str = "External service error", status_code: int | None = None
    ) -> None:
        super().__init__(
            message=message, code=f"{service.upper()}_ERROR", details={"service": service, "status_code": status_code}
        )
