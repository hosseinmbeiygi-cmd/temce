from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class CodalReportModel(TimestampMixin, Base):
    __tablename__ = "codal_reports"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    symbol: Mapped[str | None] = mapped_column(String(50), index=True)
    company_name: Mapped[str | None] = mapped_column(String(200), index=True)
    isin: Mapped[str | None] = mapped_column(String(50), index=True)
    report_type: Mapped[str | None] = mapped_column(String(50), index=True)
    fiscal_year: Mapped[str | None] = mapped_column(String(20), index=True)
    period: Mapped[str | None] = mapped_column(String(50), index=True)
    audit_status: Mapped[str | None] = mapped_column(String(20))
    publish_date: Mapped[str | None] = mapped_column(String(20))
    attachment_url: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    data_source: Mapped[str | None] = mapped_column(String(20), server_default="codal")
