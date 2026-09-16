"""Fund Universe + Symbol Aliases + Ingestion Run Audit (Additive-Only).

Revision ID: 0053
Revises: 0052
Create Date: 2026-09-16

هدف (بخش A8 سوپر-پرامپت):
  - ``fund_symbol_aliases`` : نگهداری Alias نمادها؛ تغییر نماد/ادغام/تفکیک بدون
    شکستن داده تاریخی (کلید کانونی: ISIN > national_id > symbol).
  - ``fund_universe`` (VIEW): نمای یکتای «شناسنامه + قابلیت + پوشش» هر صندوق
    بدون Dual-Write؛ کاملاً مشتق از ``funds`` + ``fund_capabilities``.
  - ``fund_ingestion_runs`` : ممیزی اجرای Discovery/Sync برای SLA و Checkpoint.
  - ``fund_meta`` : جدول متادیتای ماژول (قبلاً در Runtime ساخته می‌شد؛ اینجا
    به‌صورت رسمی و idempotent ایجاد می‌شود).

هیچ جدول/ستون موجودی حذف یا تغییر نوع نمی‌شود. اجرای دوباره idempotent است.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision: str = "0053"
down_revision: str | None = "0052"
branch_labels: str | None = None
depends_on: str | None = None

_DDL: list[str] = [
    # ── ۱. Alias نمادها (کلید کانونی مستقل از نماد) ──
    """
    CREATE TABLE IF NOT EXISTS fund_symbol_aliases (
        id            BIGSERIAL PRIMARY KEY,
        fund_id       VARCHAR(50)  NOT NULL,
        symbol        VARCHAR(80)  NOT NULL,
        isin          VARCHAR(20),
        national_id   VARCHAR(20),
        source        VARCHAR(40)  NOT NULL DEFAULT 'discovery',
        is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
        first_seen_at TIMESTAMP    DEFAULT now(),
        last_seen_at  TIMESTAMP    DEFAULT now(),
        CONSTRAINT uq_fund_alias UNIQUE (fund_id, symbol)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fund_alias_symbol ON fund_symbol_aliases (symbol)",
    "CREATE INDEX IF NOT EXISTS ix_fund_alias_isin ON fund_symbol_aliases (isin)",
    "CREATE INDEX IF NOT EXISTS ix_fund_alias_fund ON fund_symbol_aliases (fund_id, is_active)",
    # ── ۲. ممیزی اجرای همگام‌سازی (Checkpoint / SLA) ──
    """
    CREATE TABLE IF NOT EXISTS fund_ingestion_runs (
        id           BIGSERIAL PRIMARY KEY,
        run_type     VARCHAR(40)  NOT NULL,          -- discovery | nav_backfill | portfolio_backfill | score
        status       VARCHAR(20)  NOT NULL DEFAULT 'running',  -- running|success|partial|failed
        started_at   TIMESTAMP    NOT NULL DEFAULT now(),
        finished_at  TIMESTAMP,
        discovered   INTEGER      DEFAULT 0,
        created_count INTEGER     DEFAULT 0,
        updated_count INTEGER     DEFAULT 0,
        alias_count  INTEGER      DEFAULT 0,
        conflict_count INTEGER   DEFAULT 0,
        error_count  INTEGER      DEFAULT 0,
        stats_json   TEXT,
        checkpoint_json TEXT,
        error_text   VARCHAR(1000)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fund_runs_type_started ON fund_ingestion_runs (run_type, started_at DESC)",
    # ── ۳. متادیتای ماژول (رسمی‌سازی جدول Runtime) ──
    """
    CREATE TABLE IF NOT EXISTS fund_meta (
        meta_key   VARCHAR(80) PRIMARY KEY,
        meta_value TEXT,
        updated_at TIMESTAMP DEFAULT now()
    )
    """,
    # ── ۴. نمای Universe (بدون Dual-Write — کاملاً مشتق) ──
    """
    CREATE OR REPLACE VIEW fund_universe AS
    SELECT
        f.id                       AS fund_id,
        f.symbol                   AS symbol,
        f.name                     AS name,
        f.isin                     AS isin,
        f.national_id              AS national_id,
        f.fund_type                AS fund_type,
        f.sub_type                 AS sub_type,
        f.manager_name             AS manager_name,
        f.custodian_name           AS custodian_name,
        f.trading_status           AS trading_status,
        COALESCE(f.is_etf, FALSE)  AS is_etf,
        f.market_value             AS market_value,
        f.shares_count             AS shares_count,
        f.discovered_at            AS discovered_at,
        f.last_synced_at           AS last_synced_at,
        COALESCE(c.has_nav, FALSE)            AS has_nav,
        COALESCE(c.has_portfolio, FALSE)      AS has_portfolio,
        COALESCE(c.has_market_quotes, FALSE)  AS has_market_quotes,
        COALESCE(c.has_codal_reports, FALSE)  AS has_codal_reports,
        COALESCE(a.aliases_count, 0)          AS aliases_count,
        COALESCE(n.nav_points, 0)             AS nav_points,
        n.last_nav_date                       AS last_nav_date,
        p.last_portfolio_date                 AS last_portfolio_date
    FROM funds f
    LEFT JOIN fund_capabilities c ON c.fund_id = f.id
    LEFT JOIN (
        SELECT fund_id, COUNT(*) AS aliases_count
        FROM fund_symbol_aliases
        WHERE is_active = TRUE
        GROUP BY fund_id
    ) a ON a.fund_id = f.id
    LEFT JOIN (
        SELECT fund_id, COUNT(*) AS nav_points, MAX(nav_date) AS last_nav_date
        FROM fund_nav_history
        GROUP BY fund_id
    ) n ON n.fund_id = f.id
    LEFT JOIN (
        SELECT fund_id, MAX(period_end_date) AS last_portfolio_date
        FROM fund_portfolio_reports
        GROUP BY fund_id
    ) p ON p.fund_id = f.id
    """,
]


def upgrade() -> None:
    conn = op.get_bind()
    for ddl in _DDL:
        conn.execute(text(ddl))


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS fund_universe")
    op.execute("DROP TABLE IF EXISTS fund_ingestion_runs CASCADE")
    op.execute("DROP TABLE IF EXISTS fund_symbol_aliases CASCADE")
    # fund_meta عمداً باقی می‌ماند (متادیتای مشترک Runtime).
