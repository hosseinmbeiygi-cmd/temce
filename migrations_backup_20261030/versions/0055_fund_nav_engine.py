"""Fund NAV Engine + Independent Reconciliation (Additive-Only).

Revision ID: 0055
Revises: 0054
Create Date: 2026-09-18

هدف (فاز ۱ تا ۵ معماری NAV — `docs/funds/NAV_ARCHITECTURE_V5.md`):
  - ``fund_nav_runs``             : هر اجرای محاسبه NAV مستقل (نسخه‌دار + input_hash).
  - ``fund_position_valuations``  : ارزش ردیفی هر موقعیت با منبع قیمت و کیفیت.
  - ``fund_nav_results``          : NAV خالص و هر واحد (مستقل از مرجع).
  - ``fund_nav_reference_reports``: نسخه گزارش NAV مرجع (آماری/صدور/ابطال).
  - ``fund_nav_reconciliation_runs``   : نتیجه گیت‌ها + اختلاف مطلق/bps.
  - ``fund_nav_reconciliation_breaks`` : پرونده مغایرت با چرخه عمر.
  - ``fund_nav_thresholds``       : آستانه دوگانه نسخه‌دار (پیش‌فرض + هر صندوق).
  - ``fund_unit_movements``       : دفتر واحدها (صدور/ابطال/توزیع/توثیق).

هیچ جدول/ستون موجودی حذف یا تغییر نوع نمی‌شود. اجرای دوباره idempotent است.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision: str = "0055"
down_revision: str | None = "0054"
branch_labels: str | None = None
depends_on: str | None = None

_DDL: list[str] = [
    # ── ۱. اجرای محاسبه NAV مستقل ──
    """
    CREATE TABLE IF NOT EXISTS fund_nav_runs (
        id               BIGSERIAL PRIMARY KEY,
        fund_id          VARCHAR(50)  NOT NULL,
        valuation_date   DATE         NOT NULL,
        nav_type         VARCHAR(16)  NOT NULL DEFAULT 'STATISTICAL',
        mode             VARCHAR(12)  NOT NULL DEFAULT 'SHADOW',   -- SHADOW|LIVE
        engine_version   VARCHAR(32)  NOT NULL,
        policy_version   VARCHAR(32)  NOT NULL,
        input_hash       VARCHAR(64)  NOT NULL,
        run_status       VARCHAR(16)  NOT NULL DEFAULT 'SUCCESS',  -- RUNNING|SUCCESS|FAILED
        quality_status   VARCHAR(16)  NOT NULL DEFAULT 'PARTIAL',  -- COMPLETE|ESTIMATED|PARTIAL|BLOCKED
        holdings_period  DATE,
        coverage_pct     DOUBLE PRECISION,
        units_outstanding BIGINT,
        total_assets     DOUBLE PRECISION,
        total_liabilities DOUBLE PRECISION,
        net_assets       DOUBLE PRECISION,
        nav_per_unit     DOUBLE PRECISION,
        positions_count  INTEGER DEFAULT 0,
        source_json      TEXT,
        created_at       TIMESTAMP NOT NULL DEFAULT now(),
        CONSTRAINT uq_fund_nav_run UNIQUE (fund_id, valuation_date, nav_type, input_hash)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fund_nav_runs_fund_date ON fund_nav_runs (fund_id, valuation_date DESC)",
    "CREATE INDEX IF NOT EXISTS ix_fund_nav_runs_quality ON fund_nav_runs (quality_status, valuation_date DESC)",
    # ── ۲. ارزش‌گذاری ردیفی ──
    """
    CREATE TABLE IF NOT EXISTS fund_position_valuations (
        id                    BIGSERIAL PRIMARY KEY,
        run_id                BIGINT NOT NULL REFERENCES fund_nav_runs(id) ON DELETE CASCADE,
        fund_id               VARCHAR(50) NOT NULL,
        instrument_symbol     VARCHAR(80),
        instrument_name       VARCHAR(200),
        holding_type          VARCHAR(30) NOT NULL DEFAULT 'other',
        quantity              DOUBLE PRECISION,
        price                 DOUBLE PRECISION,
        price_source          VARCHAR(24),   -- snapshot|reported|model
        price_at              TIMESTAMP,
        value                 DOUBLE PRECISION,
        weight_pct            DOUBLE PRECISION,
        quality               VARCHAR(16),   -- LIVE|REPORTED|MODEL|MISSING
        reported_market_value DOUBLE PRECISION,
        note                  VARCHAR(300)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fund_pos_val_run ON fund_position_valuations (run_id)",
    "CREATE INDEX IF NOT EXISTS ix_fund_pos_val_fund ON fund_position_valuations (fund_id)",
    # ── ۳. نتیجه NAV ──
    """
    CREATE TABLE IF NOT EXISTS fund_nav_results (
        id               BIGSERIAL PRIMARY KEY,
        run_id           BIGINT NOT NULL UNIQUE REFERENCES fund_nav_runs(id) ON DELETE CASCADE,
        fund_id          VARCHAR(50) NOT NULL,
        nav_type         VARCHAR(16) NOT NULL,
        valuation_date   DATE NOT NULL,
        net_assets       DOUBLE PRECISION,
        units_outstanding BIGINT,
        nav_per_unit     DOUBLE PRECISION,
        quality_status   VARCHAR(16) NOT NULL,
        approved_by      VARCHAR(80),
        approved_at      TIMESTAMP,
        created_at       TIMESTAMP NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fund_nav_results_fund ON fund_nav_results (fund_id, valuation_date DESC)",
    # ── ۴. گزارش NAV مرجع (نسخه‌دار) ──
    """
    CREATE TABLE IF NOT EXISTS fund_nav_reference_reports (
        id               BIGSERIAL PRIMARY KEY,
        fund_id          VARCHAR(50) NOT NULL,
        nav_date         DATE NOT NULL,
        nav_type         VARCHAR(16) NOT NULL,
        nav_value        DOUBLE PRECISION NOT NULL,
        units_outstanding BIGINT,
        source           VARCHAR(40) NOT NULL DEFAULT 'fund_nav_history',
        source_ref       VARCHAR(120),
        published_at     TIMESTAMP,
        received_at      TIMESTAMP DEFAULT now(),
        recorded_at      TIMESTAMP NOT NULL DEFAULT now(),
        raw_json         TEXT,
        CONSTRAINT uq_fund_ref_report UNIQUE (fund_id, nav_date, nav_type, source)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fund_ref_reports_fund ON fund_nav_reference_reports (fund_id, nav_date DESC)",
    # ── ۵. اجرای تطبیق ──
    """
    CREATE TABLE IF NOT EXISTS fund_nav_reconciliation_runs (
        id                   BIGSERIAL PRIMARY KEY,
        fund_id              VARCHAR(50) NOT NULL,
        run_id               BIGINT REFERENCES fund_nav_runs(id) ON DELETE SET NULL,
        reference_report_id  BIGINT REFERENCES fund_nav_reference_reports(id) ON DELETE SET NULL,
        nav_type             VARCHAR(16) NOT NULL,
        valuation_date       DATE NOT NULL,
        comparability_status VARCHAR(16) NOT NULL,  -- COMPARABLE|NOT_COMPARABLE|INCOMPLETE
        reference_status     VARCHAR(12) NOT NULL,  -- VALID|STALE|INVALID
        diff_status          VARCHAR(12),           -- MATCHED|WARNING|BREACH
        internal_nav         DOUBLE PRECISION,
        reference_nav        DOUBLE PRECISION,
        abs_diff             DOUBLE PRECISION,
        bps_diff             DOUBLE PRECISION,
        abs_threshold        DOUBLE PRECISION,
        bps_threshold        DOUBLE PRECISION,
        threshold_version    VARCHAR(32),
        probable_cause       TEXT,
        residual_unexplained DOUBLE PRECISION,
        created_at           TIMESTAMP NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fund_recon_fund_date ON fund_nav_reconciliation_runs (fund_id, valuation_date DESC)",
    # ── ۶. پرونده مغایرت ──
    """
    CREATE TABLE IF NOT EXISTS fund_nav_reconciliation_breaks (
        id           BIGSERIAL PRIMARY KEY,
        recon_run_id BIGINT NOT NULL REFERENCES fund_nav_reconciliation_runs(id) ON DELETE CASCADE,
        fund_id      VARCHAR(50) NOT NULL,
        lifecycle    VARCHAR(16) NOT NULL DEFAULT 'OPEN',  -- OPEN|TRIAGED|INVESTIGATING|RESOLVED|ACCEPTED|ESCALATED
        severity     VARCHAR(12) NOT NULL DEFAULT 'WARNING',
        owner        VARCHAR(80),
        opened_at    TIMESTAMP NOT NULL DEFAULT now(),
        resolved_at  TIMESTAMP,
        sla_due_at   TIMESTAMP,
        evidence     TEXT,
        notes        TEXT,
        updated_at   TIMESTAMP NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fund_breaks_fund ON fund_nav_reconciliation_breaks (fund_id, lifecycle)",
    # ── ۷. آستانه‌های دوگانه نسخه‌دار ──
    """
    CREATE TABLE IF NOT EXISTS fund_nav_thresholds (
        id                BIGSERIAL PRIMARY KEY,
        fund_id           VARCHAR(50) NOT NULL DEFAULT '*',  -- '*' = پیش‌فرض سراسری
        nav_type          VARCHAR(16) NOT NULL DEFAULT 'STATISTICAL',
        abs_warn          DOUBLE PRECISION NOT NULL,
        abs_breach        DOUBLE PRECISION NOT NULL,
        bps_warn          DOUBLE PRECISION NOT NULL,
        bps_breach        DOUBLE PRECISION NOT NULL,
        version           VARCHAR(32) NOT NULL DEFAULT 'v1',
        effective_from    TIMESTAMP NOT NULL DEFAULT now(),
        source_document_id VARCHAR(120),
        CONSTRAINT uq_fund_nav_threshold UNIQUE (fund_id, nav_type, version)
    )
    """,
    # ── ۸. دفتر واحدها ──
    """
    CREATE TABLE IF NOT EXISTS fund_unit_movements (
        id             BIGSERIAL PRIMARY KEY,
        fund_id        VARCHAR(50) NOT NULL,
        movement_date  DATE NOT NULL,
        movement_type  VARCHAR(24) NOT NULL,   -- ISSUE|REDEEM|DISTRIBUTION|TRANSFER|PLEDGE|RELEASE
        units          DOUBLE PRECISION NOT NULL,
        price_per_unit DOUBLE PRECISION,
        amount         DOUBLE PRECISION,
        nav_type       VARCHAR(16),
        reference      VARCHAR(120),
        created_at     TIMESTAMP NOT NULL DEFAULT now(),
        CONSTRAINT uq_fund_unit_movement UNIQUE (fund_id, movement_date, movement_type, reference)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fund_unit_moves_fund ON fund_unit_movements (fund_id, movement_date DESC)",
    # ── ۹. آستانه پیش‌فرض سراسری (idempotent) ──
    """
    INSERT INTO fund_nav_thresholds
        (fund_id, nav_type, abs_warn, abs_breach, bps_warn, bps_breach, version, source_document_id)
    VALUES
        ('*', 'STATISTICAL', 1000000, 10000000, 10, 50, 'v1', 'default-bootstrap')
    ON CONFLICT (fund_id, nav_type, version) DO NOTHING
    """,
]


def upgrade() -> None:
    conn = op.get_bind()
    for ddl in _DDL:
        conn.execute(text(ddl))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS fund_unit_movements CASCADE")
    op.execute("DROP TABLE IF EXISTS fund_nav_thresholds CASCADE")
    op.execute("DROP TABLE IF EXISTS fund_nav_reconciliation_breaks CASCADE")
    op.execute("DROP TABLE IF EXISTS fund_nav_reconciliation_runs CASCADE")
    op.execute("DROP TABLE IF EXISTS fund_nav_reference_reports CASCADE")
    op.execute("DROP TABLE IF EXISTS fund_nav_results CASCADE")
    op.execute("DROP TABLE IF EXISTS fund_position_valuations CASCADE")
    op.execute("DROP TABLE IF EXISTS fund_nav_runs CASCADE")
