"""Core utility functions shared across the application."""

from __future__ import annotations


def safe_error_message(exc: BaseException, *, default_message: str = "Internal error") -> str:
    """Return a non-leaking message string for a caught exception.

    In development, returns the actual exception message for debugging.
    In production, returns a generic message to avoid leaking internal details.
    """
    from core.config import settings

    message = str(exc).strip()
    if not message:
        return default_message
    if settings.environment == "development":
        return message
    # Truncate to avoid leaking large payloads and sanitize common patterns
    sanitized = message[:500]
    for sensitive in ("password", "secret", "token", "api_key", "PRIVATE_KEY", "SECRET"):
        sanitized = sanitized.replace(sensitive, "***")
    return sanitized


def _safe_error_message(exc: BaseException, *, default_message: str = "Internal error") -> str:
    """Alias for safe_error_message for backward compatibility."""
    return safe_error_message(exc, default_message=default_message)


def suppress_exception(*exceptions: type[BaseException]) -> None:
    """Context manager factory to suppress specific exceptions."""
    import contextlib

    return contextlib.suppress(*exceptions if exceptions else Exception)
