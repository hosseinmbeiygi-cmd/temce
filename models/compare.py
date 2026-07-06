from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class CompareResultModel(TimestampMixin, Base):
    __tablename__ = "compare_results"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    total_strategies: Mapped[int] = mapped_column(default=0)
    successful: Mapped[int] = mapped_column(default=0)
    failed: Mapped[int] = mapped_column(default=0)
    best: Mapped[str | None] = mapped_column(String(100))
    worst: Mapped[str | None] = mapped_column(String(100))
    results_json: Mapped[str | None] = mapped_column(Text)
    best_return_pct: Mapped[float | None] = mapped_column(Float)
    worst_return_pct: Mapped[float | None] = mapped_column(Float)
    avg_return_pct: Mapped[float | None] = mapped_column(Float)
    start_date: Mapped[str | None] = mapped_column(String(20))
    end_date: Mapped[str | None] = mapped_column(String(20))
    capital: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(String(500))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime)
