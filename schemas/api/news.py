from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class NewsRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    from_date: date | None = None
    to_date: date | None = None
    categories: list[str] = Field(default_factory=list)
    search: str = ""
    page: int = 1
    page_size: int = 50


class NewsResponse(BaseModel):
    id: str | int
    title: str = ""
    summary: str = ""
    source: str = ""
    url: str = ""
    category: str = ""
    symbols: list[str] = Field(default_factory=list)
    published_at: str = ""
    sentiment: str = "neutral"
    sentiment_score: float = 0.0
    created_at: str = ""


class NewsListResponse(BaseModel):
    items: list[NewsResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50
