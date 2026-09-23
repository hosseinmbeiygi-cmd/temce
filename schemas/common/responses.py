from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from schemas.common.legal import LEGAL_DISCLAIMER_FA

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    error: dict[str, Any] | None = None
    message: str | None = None
    # Most payloads are plain dicts, so the envelope is the only place where the
    # disclaimer is guaranteed to reach the client for every signal/forecast.
    legal_disclaimer: str = Field(default=LEGAL_DISCLAIMER_FA)


class SuccessResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T
    message: str | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: dict[str, Any]
    message: str | None = None
