from __future__ import annotations

from pydantic import BaseModel, Field


class WatchlistCreate(BaseModel):
    name: str
    description: str = ""
    symbols: list[str] = Field(default_factory=list)


class WatchlistResponse(BaseModel):
    id: str
    name: str = ""
    description: str = ""
    symbols: list[str] = Field(default_factory=list)
    item_count: int = 0
    created_at: str = ""
    updated_at: str = ""


class WatchlistListResponse(BaseModel):
    items: list[WatchlistResponse] = Field(default_factory=list)
    total: int = 0
