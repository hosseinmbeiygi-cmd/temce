from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from core.exceptions import AppError, AuthenticationError, NotFoundError, ValidationError


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"success": False, "error": exc.message, "code": exc.code})


async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"success": False, "error": str(exc), "code": "NOT_FOUND"})


async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"success": False, "error": str(exc), "code": "VALIDATION_ERROR"})


async def auth_error_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
    return JSONResponse(status_code=401, content={"success": False, "error": str(exc), "code": "AUTH_ERROR"})


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500, content={"success": False, "error": "Internal server error", "code": "INTERNAL_ERROR"}
    )


def register_error_handlers(app):
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(NotFoundError, not_found_handler)
    app.add_exception_handler(ValidationError, validation_error_handler)
    app.add_exception_handler(AuthenticationError, auth_error_handler)
    app.add_exception_handler(Exception, generic_error_handler)
