from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class SymbolMatchMeta(BaseModel):
    """How ``?symbol=`` on /news resolved to the response items.

    ``matched`` mirrors the exact ``tag_value`` strings actually searched
    (spelling variants + persisted aliases); ``maps`` describes each
    persisted mapping row behind them so clients can surface why an item
    matched: ``exact`` / ``arabic_fallback`` / ``manual`` with its
    confidence, or an absent ``maps`` ([]) when the match ran on pure
    spelling variants alone.
    """

    symbol: str = ""
    matched: list[str] = Field(default_factory=list)
    maps: list[dict] = Field(default_factory=list)


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
    trending: bool = False


class NewsListResponse(BaseModel):
    items: list[NewsResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50
