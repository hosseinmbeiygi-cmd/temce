"""Database persistence layer for the bulk importer."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker

from bulk_importer.adapters.base import ParseResult
from bulk_importer.config import BATCH_SIZE, DATABASE_URL_SYNC, FileStatus
from bulk_importer.models import DocumentFile, DocumentTable, ImportAuditLog
from core.config import settings

logger = logging.getLogger(__name__)


class Persistence:
    """Sync SQLAlchemy persistence for the bulk importer."""

    def __init__(self, db_url: str | None = None):
        self.engine = create_engine(
            db_url or DATABASE_URL_SYNC,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            echo=False,
        )
        self.SessionLocal = sessionmaker(bind=self.engine)

    def create_tables(self) -> None:
        """Create import tables if they don't exist."""
        # Import our models to register them
        from bulk_importer import models as _m  # noqa: F401
        from models.base import Base
        Base.metadata.create_all(self.engine)
        logger.info("Import tables created/verified")

    def ensure_indexes(self) -> None:
        """Create additional indexes for performance."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS ix_import_doc_status ON import_document_files (file_status)",
            "CREATE INDEX IF NOT EXISTS ix_import_doc_symbol ON import_document_files (issuer_symbol)",
            "CREATE INDEX IF NOT EXISTS ix_import_doc_status_date ON import_document_files (file_status, report_date_jalali)",
            "CREATE INDEX IF NOT EXISTS ix_import_doc_path ON import_document_files (file_path)",
            "CREATE INDEX IF NOT EXISTS ix_import_doc_tables_file ON import_document_tables (document_file_id)",
        ]
        with self.engine.connect() as conn:
            for idx_sql in indexes:
                try:
                    conn.execute(text(idx_sql))
                except Exception as e:
                    logger.debug("Index creation note: %s", e)
            conn.commit()

    def get_or_create_document_file(
        self,
        session: Session,
        file_path: str,
        file_name: str,
        file_size: int,
        sha256: str,
        issuer_symbol: str | None,
        report_type: str | None,
        report_date_jalali: str | None,
        detected_format: str | None,
    ) -> DocumentFile | None:
        """Get existing or create new document file record. Idempotent via file_path."""
        existing = session.execute(
            select(DocumentFile).where(DocumentFile.file_path == file_path)
        ).scalar_one_or_none()

        if existing:
            return existing

        doc_values = {
            "file_name": file_name,
            "file_path": file_path,
            "file_size_bytes": file_size,
            "sha256": sha256,
            "issuer_symbol": issuer_symbol,
            "report_type": report_type,
            "report_date_jalali": report_date_jalali,
            "detected_format": detected_format,
            "file_status": FileStatus.SCANNED,
        }
        # The initial SELECT is only a fast path.  Two importer workers can
        # still pass it concurrently, so the INSERT itself must own the
        # uniqueness decision at the database boundary.
        stmt = pg_insert(DocumentFile).values(**doc_values).on_conflict_do_nothing(
            index_elements=[DocumentFile.file_path]
        )
        session.execute(stmt)
        session.flush()
        return session.execute(
            select(DocumentFile).where(DocumentFile.file_path == file_path)
        ).scalar_one_or_none()

    def save_parse_result(
        self,
        session: Session,
        doc_file: DocumentFile,
        result: ParseResult,
    ) -> None:
        """Save parse result: update DocumentFile + insert DocumentTable records."""
        doc_file.file_status = result.status
        doc_file.detected_format = result.detected_format
        doc_file.table_count = len(result.tables)
        doc_file.row_count = result.total_rows
        doc_file.parsed_at = datetime.now(UTC).replace(tzinfo=None)
        if result.errors:
            doc_file.error_message = json.dumps(result.errors, ensure_ascii=False)

        # Save tables
        for table in result.tables:
            doc_table = DocumentTable(
                document_file_id=doc_file.id,
                table_name=table.sheet_name,
                table_index=table.table_index,
                logical_section=table.logical_section,
                extraction_status="success",
                row_count=table.row_count,
                column_count=table.column_count,
                raw_json={
                    "headers": table.headers,
                    "rows": table.rows[:100],  # Keep first 100 rows as preview
                    "total_rows": table.row_count,
                },
            )
            session.add(doc_table)

    def mark_failed(self, session: Session, doc_file: DocumentFile, error: str) -> None:
        """Mark a file as failed."""
        doc_file.file_status = FileStatus.FAILED
        doc_file.error_message = error
        doc_file.parsed_at = datetime.now(UTC).replace(tzinfo=None)

    def log_audit(
        self,
        session: Session,
        batch_id: str,
        action: str,
        file_id: int | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Write an audit log entry."""
        entry = ImportAuditLog(
            batch_id=batch_id,
            action=action,
            file_id=file_id,
            message=message,
            details=details,
        )
        session.add(entry)

    def get_pending_files(self, session: Session, limit: int = BATCH_SIZE) -> list[DocumentFile]:
        """Get files that haven't been parsed yet."""
        return list(session.execute(
            select(DocumentFile)
            .where(DocumentFile.file_status == FileStatus.SCANNED)
            .limit(limit)
        ).scalars().all())

    def get_stats(self, session: Session) -> dict[str, int]:
        """Get import statistics."""
        from sqlalchemy import func

        total = session.execute(select(func.count(DocumentFile.id))).scalar() or 0
        saved = session.execute(
            select(func.count(DocumentFile.id)).where(DocumentFile.file_status == FileStatus.SAVED)
        ).scalar() or 0
        parsed = session.execute(
            select(func.count(DocumentFile.id)).where(DocumentFile.file_status == FileStatus.PARSED)
        ).scalar() or 0
        failed = session.execute(
            select(func.count(DocumentFile.id)).where(DocumentFile.file_status == FileStatus.FAILED)
        ).scalar() or 0
        skipped = session.execute(
            select(func.count(DocumentFile.id)).where(DocumentFile.file_status == FileStatus.SKIPPED_DUPLICATE)
        ).scalar() or 0
        pending = session.execute(
            select(func.count(DocumentFile.id)).where(DocumentFile.file_status == FileStatus.SCANNED)
        ).scalar() or 0

        return {
            "total": total,
            "pending": pending,
            "parsed": parsed,
            "saved": saved,
            "failed": failed,
            "skipped": skipped,
        }
