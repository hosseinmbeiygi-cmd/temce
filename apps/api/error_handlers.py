from __future__ import annotations

import traceback
import uuid
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from core.config import settings
from core.exceptions import AppError, AuthenticationError, NotFoundError, ValidationError
from core.logging import get_logger

logger = get_logger(__name__)


def _trace_id(request: Request) -> str:
    """Return trace_id from request.state (set by RequestContextMiddleware) or a fresh uuid4."""
    return getattr(request.state, "trace_id", None) or uuid.uuid4().hex


def _is_dev() -> bool:
    return settings.environment == "development" or getattr(settings, "is_development", False)


def safe_error_message(exc: BaseException, *, default_message: str = "Internal error") -> str:
    """Return a non-leaking message string for a caught exception.

    Preserves the historical ``{"message": <str>}`` response shape so existing
    clients see no breaking change. In production ``str(exc)`` is suppressed
    and a generic message is returned (the full exception is still logged via
    ``logger.exception`` by the caller). In development ``str(exc)`` is
    included for debugging.
    """
    if _is_dev():
        return str(exc) or default_message
    return default_message


def safe_error_detail(message: str | None, *, default_message: str = "Internal error") -> str:
    """Same non-leaking contract as :func:`safe_error_message`, for plain strings.

    Service layers commonly return ``Result.fail(str(exc))``; echoing
    ``result.error`` straight into an API response re-introduces the internal
    detail that ``safe_error_message`` was meant to suppress. Keep the full
    text in development, return ``default_message`` in production.
    """
    if _is_dev():
        return message or default_message
    return default_message


def error_payload(
    *,
    message: str,
    code: str,
    request: Request,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a standardized error response body.

    In production only ``success``, ``error``, and ``code`` are returned.
    In development ``trace_id`` and ``extra`` are included for diagnostics.
    """
    body: dict[str, Any] = {"success": False, "error": message, "code": code}
    if _is_dev():
        body["trace_id"] = _trace_id(request)
        if extra:
            body["extra"] = extra
    return body


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    payload = error_payload(message=exc.message, code=exc.code, request=request)
    return JSONResponse(status_code=exc.status_code, content=payload, headers={"X-Trace-Id": _trace_id(request)})


async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    payload = error_payload(message=str(exc), code="NOT_FOUND", request=request)
    return JSONResponse(status_code=404, content=payload, headers={"X-Trace-Id": _trace_id(request)})


async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    payload = error_payload(message=str(exc), code="VALIDATION_ERROR", request=request)
    return JSONResponse(status_code=422, content=payload, headers={"X-Trace-Id": _trace_id(request)})


async def auth_error_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
    payload = error_payload(message=str(exc), code="AUTH_ERROR", request=request)
    return JSONResponse(status_code=401, content=payload, headers={"X-Trace-Id": _trace_id(request)})


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    trace_id = _trace_id(request)
    logger.error("Unhandled exception on %s %s [trace=%s]: %s", request.method, request.url.path, trace_id, exc)
    logger.debug("Traceback:\n%s", traceback.format_exc())
    payload: dict[str, Any] = {"success": False, "error": "Internal server error", "code": "INTERNAL_ERROR"}
    if _is_dev():
        payload["trace_id"] = trace_id
        payload["exception"] = type(exc).__name__
    return JSONResponse(status_code=500, content=payload, headers={"X-Trace-Id": trace_id})


def register_error_handlers(app):
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(NotFoundError, not_found_handler)
    app.add_exception_handler(ValidationError, validation_error_handler)
    app.add_exception_handler(AuthenticationError, auth_error_handler)
    app.add_exception_handler(Exception, generic_error_handler)
