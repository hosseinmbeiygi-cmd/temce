"""FOF + مالیات + حاکمیت + درگاه نظارتی — ORM Models."""

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
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class FundFofValuationModel(Base):
    __tablename__ = "fund_fof_valuations"
    __table_args__ = (Index("ix_fund_fof_fund", "fund_id", "valuation_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    valuation_date: Mapped[date] = mapped_column(Date, nullable=False)
    sub_fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    sub_nav_per_unit: Mapped[float | None] = mapped_column(Double)
    units: Mapped[float | None] = mapped_column(Double)
    value: Mapped[float | None] = mapped_column(Double)
    circular_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    depth: Mapped[int] = mapped_column(Integer, default=1)
    quality: Mapped[str] = mapped_column(String(16), nullable=False, default="ESTIMATED")
    details_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class FundTaxCalculationModel(Base):
    __tablename__ = "fund_tax_calculations"
    __table_args__ = (Index("ix_fund_tax_fund", "fund_id", "tax_type"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    period_label: Mapped[str] = mapped_column(String(32), nullable=False)
    tax_type: Mapped[str] = mapped_column(String(32), nullable=False)
    base_amount: Mapped[float | None] = mapped_column(Double)
    rate: Mapped[float | None] = mapped_column(Double)
    tax_amount: Mapped[float | None] = mapped_column(Double)
    exempt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    exemption_ref: Mapped[str | None] = mapped_column(String(120))
    details_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class FundGovernanceCommitteeModel(Base):
    __tablename__ = "fund_governance_committees"
    __table_args__ = (Index("ix_fund_committees_fund", "fund_id", "committee_type"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    committee_type: Mapped[str] = mapped_column(String(40), nullable=False)
    members_json: Mapped[str | None] = mapped_column(Text)
    charter_ref: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    formed_at: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class FundInternalAuditReportModel(Base):
    __tablename__ = "fund_internal_audit_reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    period_label: Mapped[str] = mapped_column(String(32), nullable=False)
    report_date: Mapped[date | None] = mapped_column(Date)
    findings_json: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class FundDisciplinaryCaseModel(Base):
    __tablename__ = "fund_disciplinary_cases"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_role: Mapped[str] = mapped_column(String(40), nullable=False)
    subject_name: Mapped[str | None] = mapped_column(String(120))
    case_type: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="OPEN")
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(Text)


class FundInsurancePolicyModel(Base):
    __tablename__ = "fund_insurance_policies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    policy_type: Mapped[str] = mapped_column(String(40), nullable=False, default="D_AND_O")
    insurer: Mapped[str | None] = mapped_column(String(120))
    coverage_amount: Mapped[float | None] = mapped_column(Double)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    policy_ref: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class FundRegulatorAccessLogModel(Base):
    __tablename__ = "fund_regulator_access_logs"
    __table_args__ = (Index("ix_fund_regulator_logs_fund", "fund_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str | None] = mapped_column(String(50))
    endpoint: Mapped[str] = mapped_column(String(200), nullable=False)
    actor: Mapped[str | None] = mapped_column(String(120))
    purpose: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
