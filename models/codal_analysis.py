from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin


class DimCompany(Base):
    __tablename__ = "dim_company"

    company_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    company_name: Mapped[str | None] = mapped_column(String(200))
    national_id: Mapped[str | None] = mapped_column(String(30))
    industry: Mapped[str | None] = mapped_column(String(100), index=True)
    sector: Mapped[str | None] = mapped_column(String(100))
    listing_date: Mapped[str | None] = mapped_column(String(20))
    fiscal_year_end: Mapped[str | None] = mapped_column(String(10))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class DimDate(Base):
    __tablename__ = "dim_date"

    date_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    gregorian_date: Mapped[str | None] = mapped_column(String(20))
    jalali_date: Mapped[str | None] = mapped_column(String(20))
    year: Mapped[int | None] = mapped_column(Integer)
    quarter: Mapped[int | None] = mapped_column(Integer)
    month: Mapped[int | None] = mapped_column(Integer)
    is_month_end: Mapped[bool] = mapped_column(Boolean, default=False)
    is_quarter_end: Mapped[bool] = mapped_column(Boolean, default=False)
    is_year_end: Mapped[bool] = mapped_column(Boolean, default=False)


class DimAccount(Base):
    __tablename__ = "dim_account"

    account_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    canonical_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    canonical_name: Mapped[str] = mapped_column(String(200), nullable=False)
    account_category: Mapped[str | None] = mapped_column(String(50))
    statement_type: Mapped[str | None] = mapped_column(String(50))
    parent_account_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("dim_account.account_id"))
    sign_nature: Mapped[str | None] = mapped_column(String(10), default="debit")
    display_order: Mapped[int | None] = mapped_column(Integer)

    children: Mapped[list["DimAccount"]] = relationship("DimAccount", backref="parent", remote_side="DimAccount.account_id")


class DimReportType(Base):
    __tablename__ = "dim_report_type"

    report_type_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(100))
    periodicity: Mapped[str | None] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(Text)


class DimDocument(Base):
    __tablename__ = "dim_document"

    document_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    codal_tracking_id: Mapped[str | None] = mapped_column(String(100))
    company_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("dim_company.company_id"), index=True)
    report_type_id: Mapped[str | None] = mapped_column(String(20), ForeignKey("dim_report_type.report_type_id"))
    publish_date: Mapped[str | None] = mapped_column(String(20))
    fiscal_period_end: Mapped[str | None] = mapped_column(String(20))
    correction_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    correction_number: Mapped[int | None] = mapped_column(Integer, default=0)
    auditor_opinion: Mapped[str | None] = mapped_column(String(50))
    parser_version: Mapped[str | None] = mapped_column(String(20))
    raw_storage_path: Mapped[str | None] = mapped_column(Text)
    file_hash: Mapped[str | None] = mapped_column(String(100))
    document_status: Mapped[str | None] = mapped_column(String(20), default="pending")


class FactFinancials(Base):
    __tablename__ = "fact_financials"
    __table_args__ = (
        UniqueConstraint("company_id", "date_id", "account_id", "document_id", "restatement_version",
                         name="uq_fact_financials"),
    )

    fact_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    company_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("dim_company.company_id"), index=True)
    date_id: Mapped[str | None] = mapped_column(String(20), ForeignKey("dim_date.date_id"), index=True)
    account_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("dim_account.account_id"), index=True)
    document_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("dim_document.document_id"), index=True)
    report_type_id: Mapped[str | None] = mapped_column(String(20), ForeignKey("dim_report_type.report_type_id"))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str | None] = mapped_column(String(10), default="IRR")
    scale: Mapped[str | None] = mapped_column(String(10), default="RIALS")
    restatement_version: Mapped[int] = mapped_column(Integer, default=1)
    valid_from: Mapped[str | None] = mapped_column(String(20))
    valid_to: Mapped[str | None] = mapped_column(String(20))
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    validation_status: Mapped[str | None] = mapped_column(String(20), default="pending")


class FactRatios(TimestampMixin, Base):
    __tablename__ = "fact_ratios"
    __table_args__ = (
        UniqueConstraint("company_id", "date_id", "ratio_code", name="uq_fact_ratios"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    company_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("dim_company.company_id"), index=True)
    date_id: Mapped[str | None] = mapped_column(String(20), ForeignKey("dim_date.date_id"), index=True)
    ratio_code: Mapped[str] = mapped_column(String(50), index=True)
    ratio_value: Mapped[float | None] = mapped_column(Float)
    numerator: Mapped[float | None] = mapped_column(Float)
    denominator: Mapped[float | None] = mapped_column(Float)
    analysis_version: Mapped[str | None] = mapped_column(String(20))
    calculation_status: Mapped[str | None] = mapped_column(String(20))
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class FactGrowth(TimestampMixin, Base):
    __tablename__ = "fact_growth"
    __table_args__ = (
        UniqueConstraint("company_id", "date_id", "metric_code", name="uq_fact_growth"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    company_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("dim_company.company_id"), index=True)
    date_id: Mapped[str | None] = mapped_column(String(20), ForeignKey("dim_date.date_id"), index=True)
    metric_code: Mapped[str] = mapped_column(String(50), index=True)
    growth_yoy: Mapped[float | None] = mapped_column(Float)
    growth_qoq: Mapped[float | None] = mapped_column(Float)
    growth_ttm: Mapped[float | None] = mapped_column(Float)


class FactQualitySignals(TimestampMixin, Base):
    __tablename__ = "fact_quality_signals"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    company_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("dim_company.company_id"), index=True)
    date_id: Mapped[str | None] = mapped_column(String(20), ForeignKey("dim_date.date_id"), index=True)
    signal_code: Mapped[str] = mapped_column(String(50), index=True)
    signal_value: Mapped[float | None] = mapped_column(Float)
    severity: Mapped[str | None] = mapped_column(String(20))
    explanation: Mapped[str | None] = mapped_column(Text)


class FactTextAnalytics(TimestampMixin, Base):
    __tablename__ = "fact_text_analytics"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    company_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("dim_company.company_id"), index=True)
    document_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("dim_document.document_id"))
    sentiment_score: Mapped[float | None] = mapped_column(Float)
    optimism_score: Mapped[float | None] = mapped_column(Float)
    uncertainty_score: Mapped[float | None] = mapped_column(Float)
    risk_phrases: Mapped[list[str] | None] = mapped_column(JSONB)
    topic_tags: Mapped[list[str] | None] = mapped_column(JSONB)
    model_version: Mapped[str | None] = mapped_column(String(20))


class AccountMapping(Base):
    __tablename__ = "account_mappings"
    __table_args__ = (
        UniqueConstraint("source_label", "industry_scope", name="uq_account_mapping"),
    )

    mapping_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    source_label: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    normalized_label: Mapped[str | None] = mapped_column(String(300))
    canonical_account_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("dim_account.account_id"))
    account_type: Mapped[str | None] = mapped_column(String(50))
    industry_scope: Mapped[str | None] = mapped_column(String(100), default="*")
    effective_from: Mapped[str | None] = mapped_column(String(20))
    effective_to: Mapped[str | None] = mapped_column(String(20))
    mapping_version: Mapped[str | None] = mapped_column(String(20))
    confidence_level: Mapped[float | None] = mapped_column(Float)
    approved_by: Mapped[str | None] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AnalysisReport(TimestampMixin, Base):
    __tablename__ = "analysis_reports"

    report_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    company_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("dim_company.company_id"), index=True)
    symbol: Mapped[str | None] = mapped_column(String(50), index=True)
    report_type: Mapped[str | None] = mapped_column(String(20), default="professional")
    analysis_version: Mapped[str | None] = mapped_column(String(20))
    parser_version: Mapped[str | None] = mapped_column(String(20))
    mapping_version: Mapped[str | None] = mapped_column(String(20))
    scoring_version: Mapped[str | None] = mapped_column(String(20))
    report_date: Mapped[str | None] = mapped_column(String(20))
    fiscal_period: Mapped[str | None] = mapped_column(String(20))
    overall_score: Mapped[float | None] = mapped_column(Float)
    classification: Mapped[str | None] = mapped_column(String(20))
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    sections: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    alerts: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    report_pdf_path: Mapped[str | None] = mapped_column(Text)
    report_status: Mapped[str | None] = mapped_column(String(20), default="draft")
    generated_by: Mapped[str | None] = mapped_column(String(50))


class DataLineage(Base):
    __tablename__ = "data_lineage"

    lineage_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    fact_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("fact_financials.fact_id"), index=True)
    source_document_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("dim_document.document_id"))
    source_section: Mapped[str | None] = mapped_column(String(100))
    source_row_label: Mapped[str | None] = mapped_column(String(300))
    source_cell_reference: Mapped[str | None] = mapped_column(String(50))
    extraction_rule: Mapped[str | None] = mapped_column(String(100))
    parser_version: Mapped[str | None] = mapped_column(String(20))
    mapping_version: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[str | None] = mapped_column(String(30))


class AuditTrail(Base):
    __tablename__ = "audit_trail"

    audit_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(50), index=True)
    action: Mapped[str] = mapped_column(String(50), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(50))
    resource_id: Mapped[str | None] = mapped_column(String(50))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(String(50))
    timestamp: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
