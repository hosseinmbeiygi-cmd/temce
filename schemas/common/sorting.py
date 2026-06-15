from __future__ import annotations

from pydantic import BaseModel, Field


class SortParams(BaseModel):
    sort_by: str = Field(default="created_at", description="Field to sort by")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort direction: asc or desc")
