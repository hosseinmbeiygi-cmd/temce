from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    error: str | None = None
    code: str | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    code: str = "ERROR"


class PaginatedResponse(BaseModel, Generic[T]):
    success: bool = True
    data: list[T] = []
    total: int = 0
    page: int = 1
    page_size: int = 50
    total_pages: int = 1


class HealthResponse(BaseModel):
    status: str = "ok"
    timestamp: str = ""
    service: str = ""
    version: str = ""
