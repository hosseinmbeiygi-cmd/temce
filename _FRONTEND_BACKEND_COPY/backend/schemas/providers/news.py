from __future__ import annotations

from pydantic import BaseModel, Field


class NewsArticleRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    from_date: str = ""
    to_date: str = ""
    categories: list[str] = Field(default_factory=list)
    search: str = ""
    limit: int = 50


class NewsArticleResponse(BaseModel):
    id: str
    title: str = ""
    summary: str = ""
    content: str = ""
    source: str = ""
    url: str = ""
    category: str = ""
    symbols: list[str] = Field(default_factory=list)
    published_at: str = ""
    sentiment: str = "neutral"
    sentiment_score: float = 0.0
