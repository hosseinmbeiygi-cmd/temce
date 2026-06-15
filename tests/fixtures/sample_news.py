from __future__ import annotations

from datetime import datetime

from core.ids import new_id
from domain.news.news_item import NewsItem


def sample_news_article(
    id: str | None = None,
    symbol: str = "فولاد",
    category: str = "market",
) -> NewsItem:
    return NewsItem(
        id=id or new_id("news"),
        title="افزایش قیمت جهانی فولاد",
        summary="قیمت جهانی فولاد در بازارهای بین‌المللی با رشد همراه شد",
        content="بهای هر تن فولاد در بازارهای جهانی با افزایش ...",
        source="rss",
        url="https://example.com/news/123",
        category=category,
        symbols=[symbol],
        publish_date=datetime.fromisoformat("2024-01-15T10:30:00"),
        sentiment=0.85,
        sentiment_label="positive",
        data_source="rss",
    )


def sample_news_list(count: int = 5) -> list[NewsItem]:
    symbols = ["فولاد", "فملی", "وبانک", "کگل", "خودرو"]
    return [sample_news_article(symbol=symbols[i % len(symbols)]) for i in range(count)]
