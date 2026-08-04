"""SQLAlchemy models for the bulk importer audit tracking."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class DocumentFile(Base):
    """Track every file discovered and processed by the importer."""
    __tablename__ = "import_document_files"
    __table_args__ = (
        Index("ix_import_doc_status", "file_status"),
        Index("ix_import_doc_symbol", "issuer_symbol"),
        Index("ix_import_doc_path", "file_path", unique=True),
        Index("ix_import_doc_status_date", "file_status", "report_date_jalali"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    issuer_symbol: Mapped[str | None] = mapped_column(String(50))
    report_type: Mapped[str | None] = mapped_column(String(50))
    report_date_jalali: Mapped[str | None] = mapped_column(String(20))
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    detected_format: Mapped[str | None] = mapped_column(String(50))
    file_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime)
    table_count: Mapped[int] = mapped_column(Integer, default=0)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
    )


class DocumentTable(Base):
    """Each table extracted from a document file."""
    __tablename__ = "import_document_tables"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_file_id: Mapped[int] = mapped_column(ForeignKey("import_document_files.id"), index=True)
    table_name: Mapped[str | None] = mapped_column(String(100))
    table_index: Mapped[int] = mapped_column(Integer, default=0)
    logical_section: Mapped[str | None] = mapped_column(String(100))
    extraction_status: Mapped[str] = mapped_column(String(30), default="pending")
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    column_count: Mapped[int] = mapped_column(Integer, default=0)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None), server_default=func.now()
    )


class ImportAuditLog(Base):
    """Audit log for import operations."""
    __tablename__ = "import_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_id: Mapped[str | None] = mapped_column(String(50), index=True)
    action: Mapped[str] = mapped_column(String(50), index=True)
    file_id: Mapped[int | None] = mapped_column(ForeignKey("import_document_files.id"))
    message: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
