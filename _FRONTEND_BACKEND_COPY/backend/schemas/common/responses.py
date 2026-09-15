from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    error: dict[str, Any] | None = None
    message: str | None = None


class SuccessResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T
    message: str | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: dict[str, Any]
    message: str | None = None
