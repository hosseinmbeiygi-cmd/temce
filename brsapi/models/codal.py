"""
Codal announcement ORM model.

Stores announcements from the ``/Codal/Announcement.php`` endpoint.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, LargeBinary, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from brsapi.models.base import BrsApiBase, InstrumentRefMixin


class CodalAnnouncementModel(InstrumentRefMixin, BrsApiBase):
    """
    Codal announcements and reports.

    One row per announcement. Links to instruments via ``symbol``.
    """

    __tablename__ = "brsapi_codal_announcements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # ``symbol`` (l18 from Codal API) can be a long fund/institution name
    # (e.g. "انجمن خیریه حمایت از بیماران مبتلا به سرطان مهرانه استان زنجان"),
    # so it must be wider than the 50-char market symbols.
    symbol: Mapped[str | None] = mapped_column(String(200), index=True)
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
    audit_status: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="audited | unaudited")
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True, comment="SHA256 hash of stable fields for idempotency")
    fetched_at: Mapped[str | None] = mapped_column(String(30))
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_codal_content_hash"),
        Index("idx_codal_symbol_publish", "symbol", "date_publish"),
        Index("idx_codal_publish_date", "date_publish"),
    )


class CodalAttachmentModel(BrsApiBase):
    """
    Downloaded files (PDF/Excel/attachment) for a Codal announcement.

    The actual bytes can be stored in three ways, controlled by
    ``storage_type``:
    - ``local``: file is written to the configured object store path and
      ``storage_path`` holds the relative key.
    - ``s3``: file is written to S3/MinIO and ``storage_path`` holds the key.
    - ``database``: the file bytes are kept in the ``content`` column.
    """

    __tablename__ = "brsapi_codal_attachments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    announcement_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    # Same wide symbol as CodalAnnouncementModel (long fund/institution names)
    symbol: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    attachment_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="pdf | excel | attachment | html | other",
    )
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    storage_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="local",
        comment="local | s3 | database",
    )
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="pending | downloading | done | error",
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("announcement_id", "attachment_type", name="uq_codal_attachment"),
        Index("idx_codal_attachment_status", "status", "created_at"),
        Index("idx_codal_attachment_symbol", "symbol", "created_at"),
    )
