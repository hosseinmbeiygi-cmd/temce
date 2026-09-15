from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class NewsItem(BaseEntity):
    title: str
    content: str = ""
    summary: str = ""
    source: str = ""
    url: str = ""
    publish_date: datetime | None = None
    author: str = ""
    category: str = ""
    sentiment: float = 0.0
    sentiment_label: str = ""
    symbols: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    is_processed: bool = False
    data_source: str = "rss"
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        title: str,
        content: str = "",
        summary: str = "",
        source: str = "",
        url: str = "",
        publish_date: datetime | None = None,
        author: str = "",
        category: str = "",
        sentiment: float = 0.0,
        sentiment_label: str = "",
        symbols: list[str] | None = None,
        tags: list[str] | None = None,
        is_processed: bool = False,
        data_source: str = "rss",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.title = title
        self.content = content
        self.summary = summary
        self.source = source
        self.url = url
        self.publish_date = publish_date
        self.author = author
        self.category = category
        self.sentiment = sentiment
        self.sentiment_label = sentiment_label
        self.symbols = symbols or []
        self.tags = tags or []
        self.is_processed = is_processed
        self.data_source = data_source
        self.extra = extra or {}
