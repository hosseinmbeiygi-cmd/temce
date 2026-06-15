from sqlalchemy import Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class NewsArticleModel(TimestampMixin, Base):
    __tablename__ = "news_articles"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(100))
    url: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(50), index=True)
    symbols: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[str | None] = mapped_column(String(30), index=True)
    sentiment: Mapped[str | None] = mapped_column(String(20), server_default="neutral")
    sentiment_score: Mapped[float | None] = mapped_column(Float, server_default="0")
    data_source: Mapped[str | None] = mapped_column(String(20), server_default="rss")
