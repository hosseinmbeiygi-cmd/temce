"""طبقات NAV + انطباق (AML/شرعی/حاکمیت/چرخه عمر) + CSDI — ORM Models."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Double,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class FundUnitClassModel(Base):
    """🏷 پیکربندی نسخه‌دار طبقات واحد (عادی/ممتاز)."""

    __tablename__ = "fund_unit_classes"
    __table_args__ = (
        UniqueConstraint("fund_id", "class_code", "version", name="uq_fund_class"),
        Index("ix_fund_classes_fund", "fund_id", "class_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    class_code: Mapped[str] = mapped_column(String(16), nullable=False)
    class_type: Mapped[str] = mapped_column(String(16), nullable=False, default="ORDINARY")
    allocation_type: Mapped[str] = mapped_column(String(16), nullable=False, default="SIMPLE")
    units_outstanding: Mapped[int | None] = mapped_column(BigInteger)
    par_value: Mapped[float | None] = mapped_column(Double, default=1000)
    floor_rate: Mapped[float | None] = mapped_column(Double)
    ceiling_rate: Mapped[float | None] = mapped_column(Double)
    guarantee_par: Mapped[float | None] = mapped_column(Double)
    max_ratio: Mapped[float | None] = mapped_column(Double)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    effective_from: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    source_document_id: Mapped[str | None] = mapped_column(String(120))


class FundClassAllocationModel(Base):
    """📊 نتیجه تخصیص NAV بین طبقات."""

    __tablename__ = "fund_class_allocations"
    __table_args__ = (
        Index("ix_fund_class_alloc_fund", "fund_id", "valuation_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    run_id: Mapped[int | None] = mapped_column(BigInteger)
    valuation_date: Mapped[date] = mapped_column(Date, nullable=False)
    class_code: Mapped[str] = mapped_column(String(16), nullable=False)
    allocation_type: Mapped[str] = mapped_column(String(16), nullable=False)
    net_assets: Mapped[float | None] = mapped_column(Double)
    units: Mapped[int | None] = mapped_column(BigInteger)
    nav_per_unit: Mapped[float | None] = mapped_column(Double)
    transfer_amount: Mapped[float | None] = mapped_column(Double, default=0)
    quality: Mapped[str] = mapped_column(String(16), nullable=False, default="ESTIMATED")
    details_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class FundAmlAlertModel(Base):
    __tablename__ = "fund_aml_alerts"
    __table_args__ = (Index("ix_fund_aml_alerts_fund", "fund_id", "status"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(40), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(12), nullable=False, default="MEDIUM")
    subject_ref: Mapped[str | None] = mapped_column(String(120))
    amount: Mapped[float | None] = mapped_column(Double)
    evidence_json: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class FundAmlStrReportModel(Base):
    __tablename__ = "fund_aml_str_reports"
    __table_args__ = (Index("ix_fund_aml_str_fund", "fund_id", "status"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    alert_id: Mapped[int | None] = mapped_column(BigInteger)
    subject_ref: Mapped[str | None] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    amount: Mapped[float | None] = mapped_column(Double)
    due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    payload_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class FundShariaApprovalModel(Base):
    __tablename__ = "fund_sharia_approvals"
    __table_args__ = (
        UniqueConstraint("instrument_symbol", "instrument_type", "approval_ref", name="uq_sharia_approval"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    instrument_symbol: Mapped[str | None] = mapped_column(String(80))
    instrument_type: Mapped[str | None] = mapped_column(String(24))
    approval_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="APPROVED")
    notes: Mapped[str | None] = mapped_column(Text)
    effective_from: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class FundRelatedPartyTransactionModel(Base):
    __tablename__ = "fund_related_party_transactions"
    __table_args__ = (Index("ix_fund_rpt_fund", "fund_id", "transaction_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    counterparty: Mapped[str] = mapped_column(String(160), nullable=False)
    relation_type: Mapped[str | None] = mapped_column(String(60))
    amount: Mapped[float | None] = mapped_column(Double)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(120))
    disclosed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class FundComplaintModel(Base):
    __tablename__ = "fund_complaints"
    __table_args__ = (Index("ix_fund_complaints_fund", "fund_id", "lifecycle"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    channel: Mapped[str] = mapped_column(String(24), nullable=False, default="SETA")
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    tracking_code: Mapped[str | None] = mapped_column(String(80))
    lifecycle: Mapped[str] = mapped_column(String(16), nullable=False, default="OPEN")
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(Text)


class FundProspectusVersionModel(Base):
    __tablename__ = "fund_prospectus_versions"
    __table_args__ = (UniqueConstraint("fund_id", "version", name="uq_prospectus_version"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    change_type: Mapped[str] = mapped_column(String(40), nullable=False)
    changes_json: Mapped[str | None] = mapped_column(Text)
    assembly_date: Mapped[date | None] = mapped_column(Date)
    source_ref: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class FundLifecycleEventModel(Base):
    __tablename__ = "fund_lifecycle_events"
    __table_args__ = (Index("ix_fund_lifecycle_fund", "fund_id", "event_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    details_json: Mapped[str | None] = mapped_column(Text)
    source_ref: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class FundNavThresholdCalibrationModel(Base):
    __tablename__ = "fund_nav_threshold_calibrations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    nav_type: Mapped[str] = mapped_column(String(16), nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    p95_abs: Mapped[float | None] = mapped_column(Double)
    p99_abs: Mapped[float | None] = mapped_column(Double)
    p95_bps: Mapped[float | None] = mapped_column(Double)
    p99_bps: Mapped[float | None] = mapped_column(Double)
    applied_version: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class FundCsdiStatementModel(Base):
    __tablename__ = "fund_csdi_statements"
    __table_args__ = (
        UniqueConstraint("fund_id", "as_of_date", "source_ref", name="uq_csdi_statement"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    units_outstanding: Mapped[int | None] = mapped_column(BigInteger)
    source_ref: Mapped[str | None] = mapped_column(String(120))
    payload_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class FundCsdiReconciliationBreakModel(Base):
    __tablename__ = "fund_csdi_reconciliation_breaks"
    __table_args__ = (Index("ix_fund_csdi_breaks_fund", "fund_id", "status"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    internal_units: Mapped[int | None] = mapped_column(BigInteger)
    csdi_units: Mapped[int | None] = mapped_column(BigInteger)
    units_diff: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="OPEN")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
