"""
Codal announcement ORM model.

Stores announcements from the ``/Codal/Announcement.php`` endpoint.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from brsapi.models.base import BrsApiBase, InstrumentRefMixin


class CodalAnnouncementModel(InstrumentRefMixin, BrsApiBase):
    """
    Codal announcements and reports.

    One row per announcement. Links to instruments via ``symbol``.
    """

    __tablename__ = "brsapi_codal_announcements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str | None] = mapped_column(String(50), index=True)
    company_name: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str | None] = mapped_column(String(500))
    code: Mapped[str | None] = mapped_column(String(50))
    date_title: Mapped[str | None] = mapped_column(String(20))
    date_send: Mapped[str | None] = mapped_column(String(20))
    time_send: Mapped[str | None] = mapped_column(String(20))
    date_publish: Mapped[str | None] = mapped_column(String(20), index=True)
    time_publish: Mapped[str | None] = mapped_column(String(20))
    link: Mapped[str | None] = mapped_column(String(500))
    link_pdf: Mapped[str | None] = mapped_column(String(500))
    link_excel: Mapped[str | None] = mapped_column(String(500))
    link_attachment: Mapped[str | None] = mapped_column(String(500))
    fetched_at: Mapped[str | None] = mapped_column(String(30))
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_codal_symbol_publish", "symbol", "date_publish"),
        Index("idx_codal_publish_date", "date_publish"),
    )
