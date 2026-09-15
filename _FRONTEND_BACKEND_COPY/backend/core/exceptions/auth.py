from __future__ import annotations

from core.exceptions import AppError


class AuthenticationError(AppError):
    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message=message, code="AUTH_ERROR")


class AuthorizationError(AppError):
    def __init__(self, message: str = "Permission denied") -> None:
        super().__init__(message=message, code="FORBIDDEN")


class TokenExpiredError(AuthenticationError):
    def __init__(self, message: str = "Token has expired") -> None:
        super().__init__(message=message)


class InvalidTokenError(AuthenticationError):
    def __init__(self, message: str = "Invalid token") -> None:
        super().__init__(message=message)


class InvalidAPIKeyError(AuthenticationError):
    def __init__(self, message: str = "Invalid API key") -> None:
        super().__init__(message=message)


class InsufficientPermissionsError(AuthorizationError):
    def __init__(self, message: str = "Insufficient permissions", required: list[str] | None = None) -> None:
        details = {"required": required or []}
        super().__init__(message=message)
        self.details = details
