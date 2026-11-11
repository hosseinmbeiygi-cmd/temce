"""Tiered NAV + AML/Sharia + Governance + Lifecycle + Calibration + CSDI (Additive-Only).

Revision ID: 0057
Revises: 0056
Create Date: 2026-09-18

هدف (فازهای ۴، ۷، ۸، ۹ + کالیبراسیون + CSDI):
  - ``fund_unit_classes``            : پیکربندی نسخه‌دار طبقات (عادی/ممتاز، کف/سقف، تضمین).
  - ``fund_class_allocations``       : نتیجه تخصیص NAV بین طبقات.
  - ``fund_aml_alerts``              : هشدارهای AML (کم/متوسط/پرریسک).
  - ``fund_aml_str_reports``         : گزارش معاملات مشکوک با مهلت و وضعیت.
  - ``fund_sharia_approvals``        : تأیید شرعی ابزار/عملیات (کمیته فقهی).
  - ``fund_related_party_transactions`` : معاملات با اشخاص وابسته (تصویب/افشا).
  - ``fund_complaints``              : شکایات (سمتا/داوری) با چرخه عمر.
  - ``fund_prospectus_versions``     : نسخه‌های امیدنامه و تغییرات پارامتری.
  - ``fund_lifecycle_events``        : رویدادهای چرخه عمر صندوق.
  - ``fund_nav_threshold_calibrations`` : سابقه کالیبراسیون آستانه‌ها.
  - ``fund_csdi_statements``         : صورت‌وضعیت واحدها از CSDI.
  - ``fund_csdi_reconciliation_breaks`` : مغایرت واحد بین CSDI و دفتر.

هیچ جدول/ستون موجودی حذف یا تغییر نوع نمی‌شود. اجرای دوباره idempotent است.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision: str = "0057"
down_revision: str | None = "0056"
branch_labels: str | None = None
depends_on: str | None = None

_DDL: list[str] = [
    # ── فاز ۴: طبقات واحد ──
    """
    CREATE TABLE IF NOT EXISTS fund_unit_classes (
        id                 BIGSERIAL PRIMARY KEY,
        fund_id            VARCHAR(50) NOT NULL,
        class_code         VARCHAR(16) NOT NULL,       -- ORDINARY|PREFERRED|PREFERRED_SPECIAL
        class_type         VARCHAR(16) NOT NULL DEFAULT 'ORDINARY',
        allocation_type    VARCHAR(16) NOT NULL DEFAULT 'SIMPLE', -- SIMPLE|LEVERAGED|GUARANTEED|FOF
        units_outstanding  BIGINT,
        par_value          DOUBLE PRECISION DEFAULT 1000,
        floor_rate         DOUBLE PRECISION,           -- نرخ کف سالانه (اعشاری)
        ceiling_rate       DOUBLE PRECISION,           -- نرخ سقف سالانه (اعشاری)
        guarantee_par      DOUBLE PRECISION,           -- ارزش اسمی تضمین‌شده
        max_ratio          DOUBLE PRECISION,           -- سقف نسبت (مثلاً ۲ برابر)
        version            VARCHAR(32) NOT NULL DEFAULT 'v1',
        effective_from     TIMESTAMP NOT NULL DEFAULT now(),
        source_document_id VARCHAR(120),
        CONSTRAINT uq_fund_class UNIQUE (fund_id, class_code, version)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fund_classes_fund ON fund_unit_classes (fund_id, class_code)",
    """
    CREATE TABLE IF NOT EXISTS fund_class_allocations (
        id              BIGSERIAL PRIMARY KEY,
        fund_id         VARCHAR(50) NOT NULL,
        run_id          BIGINT REFERENCES fund_nav_runs(id) ON DELETE SET NULL,
        valuation_date  DATE NOT NULL,
        class_code      VARCHAR(16) NOT NULL,
        allocation_type VARCHAR(16) NOT NULL,
        net_assets      DOUBLE PRECISION,
        units           BIGINT,
        nav_per_unit    DOUBLE PRECISION,
        transfer_amount DOUBLE PRECISION DEFAULT 0,
        quality         VARCHAR(16) NOT NULL DEFAULT 'ESTIMATED',
        details_json    TEXT,
        created_at      TIMESTAMP NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fund_class_alloc_fund ON fund_class_allocations (fund_id, valuation_date DESC)",
    # ── فاز ۷: AML ──
    """
    CREATE TABLE IF NOT EXISTS fund_aml_alerts (
        id            BIGSERIAL PRIMARY KEY,
        fund_id       VARCHAR(50) NOT NULL,
        alert_type    VARCHAR(40) NOT NULL,
        risk_level    VARCHAR(12) NOT NULL DEFAULT 'MEDIUM',  -- LOW|MEDIUM|HIGH
        subject_ref   VARCHAR(120),
        amount        DOUBLE PRECISION,
        evidence_json TEXT,
        status        VARCHAR(16) NOT NULL DEFAULT 'OPEN',     -- OPEN|REVIEWED|REPORTED|DISMISSED
        created_at    TIMESTAMP NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fund_aml_alerts_fund ON fund_aml_alerts (fund_id, status)",
    """
    CREATE TABLE IF NOT EXISTS fund_aml_str_reports (
        id            BIGSERIAL PRIMARY KEY,
        fund_id       VARCHAR(50) NOT NULL,
        alert_id      BIGINT REFERENCES fund_aml_alerts(id) ON DELETE SET NULL,
        subject_ref   VARCHAR(120),
        reason        VARCHAR(300) NOT NULL,
        amount        DOUBLE PRECISION,
        due_at        TIMESTAMP NOT NULL,
        submitted_at  TIMESTAMP,
        status        VARCHAR(16) NOT NULL DEFAULT 'DRAFT',    -- DRAFT|SUBMITTED|ACCEPTED
        payload_json  TEXT,
        created_at    TIMESTAMP NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fund_aml_str_fund ON fund_aml_str_reports (fund_id, status)",
    # ── فاز ۷: انطباق شرعی ──
    """
    CREATE TABLE IF NOT EXISTS fund_sharia_approvals (
        id              BIGSERIAL PRIMARY KEY,
        instrument_symbol VARCHAR(80),
        instrument_type VARCHAR(24),
        approval_ref    VARCHAR(120) NOT NULL,
        status          VARCHAR(16) NOT NULL DEFAULT 'APPROVED', -- APPROVED|REJECTED|PENDING
        notes           TEXT,
        effective_from  TIMESTAMP NOT NULL DEFAULT now(),
        recorded_at     TIMESTAMP NOT NULL DEFAULT now(),
        CONSTRAINT uq_sharia_approval UNIQUE (instrument_symbol, instrument_type, approval_ref)
    )
    """,
    # ── فاز ۸: حاکمیت/حقوقی ──
    """
    CREATE TABLE IF NOT EXISTS fund_related_party_transactions (
        id             BIGSERIAL PRIMARY KEY,
        fund_id        VARCHAR(50) NOT NULL,
        counterparty   VARCHAR(160) NOT NULL,
        relation_type  VARCHAR(60),
        amount         DOUBLE PRECISION,
        transaction_date DATE NOT NULL,
        approved_by    VARCHAR(120),
        disclosed      BOOLEAN NOT NULL DEFAULT FALSE,
        notes          TEXT,
        created_at     TIMESTAMP NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fund_rpt_fund ON fund_related_party_transactions (fund_id, transaction_date DESC)",
    """
    CREATE TABLE IF NOT EXISTS fund_complaints (
        id             BIGSERIAL PRIMARY KEY,
        fund_id        VARCHAR(50) NOT NULL,
        channel        VARCHAR(24) NOT NULL DEFAULT 'SETA',   -- SETA|ARBITRATION|INTERNAL
        subject        VARCHAR(300) NOT NULL,
        tracking_code  VARCHAR(80),
        lifecycle      VARCHAR(16) NOT NULL DEFAULT 'OPEN',
        opened_at      TIMESTAMP NOT NULL DEFAULT now(),
        resolved_at    TIMESTAMP,
        notes          TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fund_complaints_fund ON fund_complaints (fund_id, lifecycle)",
    # ── فاز ۹: امیدنامه و چرخه عمر ──
    """
    CREATE TABLE IF NOT EXISTS fund_prospectus_versions (
        id             BIGSERIAL PRIMARY KEY,
        fund_id        VARCHAR(50) NOT NULL,
        version        VARCHAR(32) NOT NULL,
        change_type    VARCHAR(40) NOT NULL,   -- FEE|CAPS|MARKET_MAKING|MANAGER|CUSTODIAN|OTHER
        changes_json   TEXT,
        assembly_date  DATE,
        source_ref     VARCHAR(120),
        created_at     TIMESTAMP NOT NULL DEFAULT now(),
        CONSTRAINT uq_prospectus_version UNIQUE (fund_id, version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fund_lifecycle_events (
        id           BIGSERIAL PRIMARY KEY,
        fund_id      VARCHAR(50) NOT NULL,
        event_type   VARCHAR(32) NOT NULL,   -- INCEPTION|RENEWAL|CAP_INCREASE|MERGER|LIQUIDATION|CONVERSION
        event_date   DATE NOT NULL,
        details_json TEXT,
        source_ref   VARCHAR(120),
        created_at   TIMESTAMP NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fund_lifecycle_fund ON fund_lifecycle_events (fund_id, event_date DESC)",
    # ── کالیبراسیون آستانه ──
    """
    CREATE TABLE IF NOT EXISTS fund_nav_threshold_calibrations (
        id             BIGSERIAL PRIMARY KEY,
        fund_id        VARCHAR(50) NOT NULL,
        nav_type       VARCHAR(16) NOT NULL,
        sample_size    INTEGER NOT NULL,
        p95_abs        DOUBLE PRECISION,
        p99_abs        DOUBLE PRECISION,
        p95_bps        DOUBLE PRECISION,
        p99_bps        DOUBLE PRECISION,
        applied_version VARCHAR(32),
        created_at     TIMESTAMP NOT NULL DEFAULT now()
    )
    """,
    # ── CSDI ──
    """
    CREATE TABLE IF NOT EXISTS fund_csdi_statements (
        id               BIGSERIAL PRIMARY KEY,
        fund_id          VARCHAR(50) NOT NULL,
        as_of_date       DATE NOT NULL,
        units_outstanding BIGINT,
        source_ref       VARCHAR(120),
        payload_json     TEXT,
        created_at       TIMESTAMP NOT NULL DEFAULT now(),
        CONSTRAINT uq_csdi_statement UNIQUE (fund_id, as_of_date, source_ref)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fund_csdi_reconciliation_breaks (
        id            BIGSERIAL PRIMARY KEY,
        fund_id       VARCHAR(50) NOT NULL,
        as_of_date    DATE NOT NULL,
        internal_units BIGINT,
        csdi_units    BIGINT,
        units_diff    BIGINT,
        status        VARCHAR(16) NOT NULL DEFAULT 'OPEN',
        notes         TEXT,
        created_at    TIMESTAMP NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fund_csdi_breaks_fund ON fund_csdi_reconciliation_breaks (fund_id, status)",
]


def upgrade() -> None:
    conn = op.get_bind()
    for ddl in _DDL:
        conn.execute(text(ddl))


def downgrade() -> None:
    for table in (
        "fund_csdi_reconciliation_breaks",
        "fund_csdi_statements",
        "fund_nav_threshold_calibrations",
        "fund_lifecycle_events",
        "fund_prospectus_versions",
        "fund_complaints",
        "fund_related_party_transactions",
        "fund_sharia_approvals",
        "fund_aml_str_reports",
        "fund_aml_alerts",
        "fund_class_allocations",
        "fund_unit_classes",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
