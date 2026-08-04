from sqlalchemy import BigInteger, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class CodalAuditSummaryModel(Base):
    """Audit/financial-health summary per symbol (created by scripts/batch_audit_all_symbols.py).

    One row per symbol. Added so services (e.g. multi_market_signal_engine)
    can read it through the ORM instead of raw ``text()`` SQL.
    """

    __tablename__ = "codal_audit_summary"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    company_name: Mapped[str | None] = mapped_column(String(200))
    report_type: Mapped[str | None] = mapped_column(String(20))
    report_date: Mapped[str | None] = mapped_column(String(20))
    revenue: Mapped[float | None] = mapped_column(Float)
    net_profit: Mapped[float | None] = mapped_column(Float)
    total_assets: Mapped[float | None] = mapped_column(Float)
    total_equity: Mapped[float | None] = mapped_column(Float)
    eps: Mapped[float | None] = mapped_column(Float)
    roe: Mapped[float | None] = mapped_column(Float)
    roa: Mapped[float | None] = mapped_column(Float)
    gross_margin: Mapped[float | None] = mapped_column(Float)
    net_margin: Mapped[float | None] = mapped_column(Float)
    current_ratio: Mapped[float | None] = mapped_column(Float)
    debt_to_equity: Mapped[float | None] = mapped_column(Float)
    asset_turnover: Mapped[float | None] = mapped_column(Float)
    revenue_growth: Mapped[float | None] = mapped_column(Float)
    net_profit_growth: Mapped[float | None] = mapped_column(Float)
    health_score: Mapped[float | None] = mapped_column(Float)
    health_classification: Mapped[str | None] = mapped_column(String(20))
    earnings_quality_score: Mapped[float | None] = mapped_column(Float)
    forensic_risk: Mapped[str | None] = mapped_column(String(20))
    going_concern_risk: Mapped[str | None] = mapped_column(String(20))
    materiality_planning: Mapped[float | None] = mapped_column(Float)
    materiality_performance: Mapped[float | None] = mapped_column(Float)
    top_audit_risks: Mapped[dict | list | None] = mapped_column(JSONB)
    total_reports: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    analysis_status: Mapped[str | None] = mapped_column(String(20))
    full_results: Mapped[dict | list | None] = mapped_column(JSONB)


class CodalReportModel(TimestampMixin, Base):
    __tablename__ = "codal_reports"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    instrument_id: Mapped[str | None] = mapped_column(String(50), index=True)
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
