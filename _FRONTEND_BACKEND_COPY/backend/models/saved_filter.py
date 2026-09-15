from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class SavedFilter(TimestampMixin, Base):
    """Saved screener filter for a user."""

    __tablename__ = "saved_filters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    filters_json: Mapped[str] = mapped_column(Text, nullable=False)
    logic: Mapped[str] = mapped_column(String(10), nullable=False, server_default=sa.text("'and'"))
    sort_by: Mapped[str] = mapped_column(String(50), nullable=False, server_default=sa.text("'smc_score'"))
    sort_order: Mapped[str] = mapped_column(String(10), nullable=False, server_default=sa.text("'desc'"))
    market: Mapped[str | None] = mapped_column(String(50))
    min_score: Mapped[float] = mapped_column(sa.Float, nullable=False, server_default=sa.text("0.0"))
    is_default: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.text("false"))
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa.text("0"))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
