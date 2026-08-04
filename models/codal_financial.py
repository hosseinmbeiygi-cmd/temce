from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class CodalFinancialStatementModel(TimestampMixin, Base):
    __tablename__ = "codal_financial_statements"
    __table_args__ = (
        UniqueConstraint(
            "symbol", "report_type", "report_date",
            name="uq_codal_financial_symbol_type_date",
        ),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    report_type: Mapped[str | None] = mapped_column(String(20), index=True)
    report_date: Mapped[str | None] = mapped_column(String(20), index=True)
    filename: Mapped[str | None] = mapped_column(String(200))
    file_path: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    parsed_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    table_count: Mapped[int | None] = mapped_column(default=0)
    row_count: Mapped[int | None] = mapped_column(default=0)
    import_batch: Mapped[str | None] = mapped_column(String(50), index=True)
    imported_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now()
    )
