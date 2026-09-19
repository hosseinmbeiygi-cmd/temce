"""دفتر مالی دوطرفه + Outbox — ORM Models (Additive-Only).

جداول:
  - chart_of_accounts → کدینگ حساب‌ها
  - journal_entries   → سند مالی (idempotent + برگشت + منبع)
  - journal_lines     → خطوط بدهکار/بستانکار با قید علامت
  - fund_nav_outbox   → Outbox رویدادها در هم‌تراکنش با دفتر

توازن هر سند در DB با Constraint Trigger تعویق‌شده اجبار می‌شود (migration 0056).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class ChartOfAccountModel(Base):
    """📚 کدینگ حساب‌های استاندارد صندوق."""

    __tablename__ = "chart_of_accounts"

    account_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    account_name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_type: Mapped[str] = mapped_column(String(24), nullable=False)
    normal_side: Mapped[str] = mapped_column(String(8), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class JournalEntryModel(Base):
    """🧾 سند مالی — وضعیت POSTED/REVERSED و کلید idempotency."""

    __tablename__ = "journal_entries"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_journal_idem"),
        UniqueConstraint("source_system", "source_ref_id", name="uq_journal_source"),
        Index("ix_journal_entries_fund", "fund_id", "effective_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="POSTED")
    effective_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    source_system: Mapped[str | None] = mapped_column(String(32))
    source_ref_id: Mapped[str | None] = mapped_column(String(128))
    reverses_entry_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("journal_entries.id")
    )
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    memo: Mapped[str | None] = mapped_column(String(300))


class JournalLineModel(Base):
    """📄 خط سند — بدهکار/بستانکار + مقدار."""

    __tablename__ = "journal_lines"
    __table_args__ = (
        Index("ix_journal_lines_entry", "entry_id"),
        Index("ix_journal_lines_account", "fund_id", "account_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entry_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False
    )
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    account_code: Mapped[str] = mapped_column(
        String(32), ForeignKey("chart_of_accounts.account_code"), nullable=False
    )
    instrument_symbol: Mapped[str | None] = mapped_column(String(80))
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="IRR")
    debit_amount: Mapped[float] = mapped_column(Numeric(28, 2), nullable=False, default=0)
    credit_amount: Mapped[float] = mapped_column(Numeric(28, 2), nullable=False, default=0)
    quantity_delta: Mapped[float] = mapped_column(Numeric(24, 6), nullable=False, default=0)
    memo: Mapped[str | None] = mapped_column(String(300))


class FundNavOutboxModel(Base):
    """📤 Outbox رویدادها — نوشتن در هم‌تراکنش با دفتر، انتشار at-least-once."""

    __tablename__ = "fund_nav_outbox"
    __table_args__ = (
        Index("ix_fund_outbox_status", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    fund_id: Mapped[str | None] = mapped_column(String(50))
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
