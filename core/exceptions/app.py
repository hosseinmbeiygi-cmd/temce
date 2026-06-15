from __future__ import annotations

from typing import Any

from core.exceptions import AppError


class StartupError(AppError):
    def __init__(self, message: str = "Application startup failed", component: str | None = None) -> None:
        super().__init__(message=message, code="STARTUP_ERROR", details={"component": component})


class ShutdownError(AppError):
    def __init__(self, message: str = "Application shutdown failed", component: str | None = None) -> None:
        super().__init__(message=message, code="SHUTDOWN_ERROR", details={"component": component})


class InitializationError(AppError):
    def __init__(self, message: str = "Initialization failed", details: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code="INIT_ERROR", details=details)


class GracefulShutdownError(AppError):
    def __init__(self, message: str = "Graceful shutdown failed", timeout: float | None = None) -> None:
        super().__init__(message=message, code="GRACEFUL_SHUTDOWN_ERROR", details={"timeout": timeout})
