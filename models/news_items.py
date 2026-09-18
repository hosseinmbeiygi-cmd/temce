"""ORM models for the new news schema (migration 0054).

Read-side only: these classes mirror the DDL exactly (naive timestamps,
BIGSERIAL ids; the partial-unique dedup index lives in the DB, not here).
The write path keeps using the legacy ORM (``models.news.NewsArticleModel``)
plus ``services.news_dual_write`` — nothing writes through these models,
so they can never drift the pipeline.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class NewsItemModel(Base):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    legacy_article_id: Mapped[str | None] = mapped_column(String(50), unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(100))
    source_url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    category: Mapped[str | None] = mapped_column(String(50))
    is_breaking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dedup_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_news_published", "published_at"),
        Index("idx_news_category", "category"),
        Index("idx_news_source", "source"),
    )


class NewsTagModel(Base):
    __tablename__ = "news_tags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    news_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    tag_type: Mapped[str | None] = mapped_column(String(20))
    tag_value: Mapped[str | None] = mapped_column(String(50))
    confidence: Mapped[float | None] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


__all__ = ["NewsItemModel", "NewsTagModel"]
