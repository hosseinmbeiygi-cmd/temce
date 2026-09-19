"""FOF + Tax + Governance + Regulator Portal (Additive-Only).

Revision ID: 0058
Revises: 0057
Create Date: 2026-09-18

هدف (تکمیل فازهای ۴، ۷، ۸، ۹ و ۱۰):
  - ``fund_fof_valuations``        : ارزش‌گذاری فراصندوق از NAV زیرصندوق‌ها + کشف حلقه.
  - ``fund_tax_calculations``      : محاسبات مالیاتی (مقطوع ۰.۵٪، CGT، سود سپرده).
  - ``fund_governance_committees`` : کمیته‌های حاکمیتی.
  - ``fund_internal_audit_reports``: گزارش‌های حسابرسی داخلی.
  - ``fund_disciplinary_cases``    : پرونده‌های انتظامی.
  - ``fund_insurance_policies``    : بیمه مسئولیت حرفه‌ای (D&O).
  - ``fund_regulator_access_logs`` : لاگ دسترسی درگاه نظارتی (append-only).

هیچ جدول/ستون موجودی حذف یا تغییر نوع نمی‌شود. اجرای دوباره idempotent است.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision: str = "0058"
down_revision: str | None = "0057"
branch_labels: str | None = None
depends_on: str | None = None

_DDL: list[str] = [
    # ── FOF ──
    """
    CREATE TABLE IF NOT EXISTS fund_fof_valuations (
        id               BIGSERIAL PRIMARY KEY,
        fund_id          VARCHAR(50) NOT NULL,
        valuation_date   DATE NOT NULL,
        sub_fund_id      VARCHAR(50) NOT NULL,
        sub_nav_per_unit DOUBLE PRECISION,
        units            DOUBLE PRECISION,
        value            DOUBLE PRECISION,
        circular_flag    BOOLEAN NOT NULL DEFAULT FALSE,
        depth            INTEGER DEFAULT 1,
        quality          VARCHAR(16) NOT NULL DEFAULT 'ESTIMATED',
        details_json     TEXT,
        created_at       TIMESTAMP NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fund_fof_fund ON fund_fof_valuations (fund_id, valuation_date DESC)",
    # ── Tax ──
    """
    CREATE TABLE IF NOT EXISTS fund_tax_calculations (
        id            BIGSERIAL PRIMARY KEY,
        fund_id       VARCHAR(50) NOT NULL,
        period_label  VARCHAR(32) NOT NULL,
        tax_type      VARCHAR(32) NOT NULL,   -- TRANSFER_05|CGT|DEPOSIT_INTEREST|VAT
        base_amount   DOUBLE PRECISION,
        rate          DOUBLE PRECISION,
        tax_amount    DOUBLE PRECISION,
        exempt        BOOLEAN NOT NULL DEFAULT TRUE,
        exemption_ref VARCHAR(120),
        details_json  TEXT,
        created_at    TIMESTAMP NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fund_tax_fund ON fund_tax_calculations (fund_id, tax_type)",
    # ── Governance ──
    """
    CREATE TABLE IF NOT EXISTS fund_governance_committees (
        id            BIGSERIAL PRIMARY KEY,
        fund_id       VARCHAR(50) NOT NULL,
        committee_type VARCHAR(40) NOT NULL,  -- AUDIT|RISK|NOMINATION|VALUATION|OTHER
        members_json  TEXT,
        charter_ref   VARCHAR(120),
        is_active     BOOLEAN NOT NULL DEFAULT TRUE,
        formed_at     DATE,
        created_at    TIMESTAMP NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fund_committees_fund ON fund_governance_committees (fund_id, committee_type)",
    """
    CREATE TABLE IF NOT EXISTS fund_internal_audit_reports (
        id            BIGSERIAL PRIMARY KEY,
        fund_id       VARCHAR(50) NOT NULL,
        period_label  VARCHAR(32) NOT NULL,
        report_date   DATE,
        findings_json TEXT,
        status        VARCHAR(16) NOT NULL DEFAULT 'OPEN',
        created_at    TIMESTAMP NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fund_disciplinary_cases (
        id            BIGSERIAL PRIMARY KEY,
        fund_id       VARCHAR(50) NOT NULL,
        subject_role  VARCHAR(40) NOT NULL,
        subject_name  VARCHAR(120),
        case_type     VARCHAR(60) NOT NULL,
        status        VARCHAR(16) NOT NULL DEFAULT 'OPEN',
        opened_at     TIMESTAMP NOT NULL DEFAULT now(),
        closed_at     TIMESTAMP,
        notes         TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fund_insurance_policies (
        id               BIGSERIAL PRIMARY KEY,
        fund_id          VARCHAR(50) NOT NULL,
        policy_type      VARCHAR(40) NOT NULL DEFAULT 'D_AND_O',
        insurer          VARCHAR(120),
        coverage_amount  DOUBLE PRECISION,
        valid_from       DATE,
        valid_to         DATE,
        policy_ref       VARCHAR(120),
        created_at       TIMESTAMP NOT NULL DEFAULT now()
    )
    """,
    # ── Regulator Portal ──
    """
    CREATE TABLE IF NOT EXISTS fund_regulator_access_logs (
        id         BIGSERIAL PRIMARY KEY,
        fund_id    VARCHAR(50),
        endpoint   VARCHAR(200) NOT NULL,
        actor      VARCHAR(120),
        purpose    VARCHAR(200),
        created_at TIMESTAMP NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fund_regulator_logs_fund ON fund_regulator_access_logs (fund_id, created_at DESC)",
]


def upgrade() -> None:
    conn = op.get_bind()
    for ddl in _DDL:
        conn.execute(text(ddl))


def downgrade() -> None:
    for table in (
        "fund_regulator_access_logs",
        "fund_insurance_policies",
        "fund_disciplinary_cases",
        "fund_internal_audit_reports",
        "fund_governance_committees",
        "fund_tax_calculations",
        "fund_fof_valuations",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
