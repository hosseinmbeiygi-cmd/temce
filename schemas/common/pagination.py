from __future__ import annotations

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=50, ge=1, le=500, description="Items per page")


class PaginatedResponse(BaseModel):
    items: list = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1)
    total_pages: int = Field(default=0, ge=0)
    has_next: bool = False
    has_prev: bool = False
