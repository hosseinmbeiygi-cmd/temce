"""Enterprise Fund Module — additive tables & columns (Zero Breaking Changes).

Revision ID: 0051
Revises: 0050
Create Date: 2026-09-16

طراحی کاملاً افزایشی (Additive-Only):
  - هیچ جدول یا ستون موجودی حذف یا تغییر نوع نمی‌کند.
  - روی جدول ``funds`` موجود فقط ستون‌های nullable اضافه می‌شود.
  - جداول جدید با IF NOT EXISTS ساخته می‌شوند تا اجرای مجدد idempotent باشد.
  - کلید کانونی صندوق: اولاً ISIN، ثانیاً national_id (مستقل از نماد).
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision: str = "0051"
down_revision: str | None = "0050"
branch_labels: str | None = None
depends_on: str | None = None

# ── DDL ──────────────────────────────────────────────────────────────────────

_FUNDS_ADDITIVE_COLUMNS = [
    # (column, ddl)
    ("national_id", "VARCHAR(20)"),          # شناسه ملی صندوق (ثانویه بعد از ISIN)
    ("manager_name", "VARCHAR(200)"),        # مدیر صندوق
    ("custodian_name", "VARCHAR(200)"),      # متولی صندوق
    ("trading_status", "VARCHAR(20)"),       # active | suspended | terminated
    ("is_etf", "BOOLEAN DEFAULT FALSE"),
    ("discovered_at", "TIMESTAMP"),          # زمان کشف خودکار از Universe API
    ("last_synced_at", "TIMESTAMP"),         # آخرین همگام‌سازی موفق
]

_NEW_TABLES: list[tuple[str, str]] = [
    # ── ۱. قابلیت‌های تشخیصی هر صندوق ──
    (
        "fund_capabilities",
        """
        CREATE TABLE IF NOT EXISTS fund_capabilities (
            id            BIGSERIAL PRIMARY KEY,
            fund_id       VARCHAR(50)  NOT NULL,
            isin          VARCHAR(20),
            has_nav           BOOLEAN NOT NULL DEFAULT FALSE,
            has_portfolio     BOOLEAN NOT NULL DEFAULT FALSE,
            is_etf            BOOLEAN NOT NULL DEFAULT FALSE,
            has_market_quotes BOOLEAN NOT NULL DEFAULT FALSE,
            has_codal_reports BOOLEAN NOT NULL DEFAULT FALSE,
            capabilities_json TEXT,
            updated_at    TIMESTAMP DEFAULT now(),
            created_at    TIMESTAMP DEFAULT now(),
            CONSTRAINT uq_fund_capabilities_fund UNIQUE (fund_id)
        )
        """,
    ),
    # ── ۲. تاریخچه NAV (idempotent روی fund_id + nav_date) ──
    (
        "fund_nav_history",
        """
        CREATE TABLE IF NOT EXISTS fund_nav_history (
            id            BIGSERIAL PRIMARY KEY,
            fund_id       VARCHAR(50)  NOT NULL,
            isin          VARCHAR(20),
            nav_date      DATE         NOT NULL,
            nav_date_greg DATE,
            nav_issue     DOUBLE PRECISION,   -- NAV صدور
            nav_redemption DOUBLE PRECISION,  -- NAV ابطال
            nav_statistical DOUBLE PRECISION, -- قیمت آماری
            total_asset_value DOUBLE PRECISION, -- ارزش کل دارایی‌ها
            units_outstanding BIGINT,
            data_source   VARCHAR(30) NOT NULL DEFAULT 'api',
            payload_version SMALLINT NOT NULL DEFAULT 1,
            created_at    TIMESTAMP DEFAULT now(),
            updated_at    TIMESTAMP DEFAULT now(),
            CONSTRAINT uq_fund_nav UNIQUE (fund_id, nav_date)
        )
        """,
    ),
    # ── ۳. سربرگ گزارش‌های ماهانه کدال (period-ending based) ──
    (
        "fund_portfolio_reports",
        """
        CREATE TABLE IF NOT EXISTS fund_portfolio_reports (
            id            BIGSERIAL PRIMARY KEY,
            fund_id       VARCHAR(50) NOT NULL,
            isin          VARCHAR(20),
            period_end_date      DATE NOT NULL,   -- دوره منتهی به
            period_end_date_greg DATE,
            publish_date         DATE,
            codal_letter_id      VARCHAR(50),
            report_title         VARCHAR(300),
            total_assets         DOUBLE PRECISION,
            total_liabilities    DOUBLE PRECISION,
            net_asset_value      DOUBLE PRECISION,
            units_outstanding    BIGINT,
            cash_and_equivalents DOUBLE PRECISION,
            data_source   VARCHAR(30) NOT NULL DEFAULT 'api',
            payload_version SMALLINT NOT NULL DEFAULT 1,
            created_at    TIMESTAMP DEFAULT now(),
            updated_at    TIMESTAMP DEFAULT now(),
            CONSTRAINT uq_fund_report_period UNIQUE (fund_id, period_end_date)
        )
        """,
    ),
    # ── ۴. ریز دارایی‌های صندوق ──
    (
        "fund_holdings",
        """
        CREATE TABLE IF NOT EXISTS fund_holdings (
            id            BIGSERIAL PRIMARY KEY,
            fund_id       VARCHAR(50) NOT NULL,
            report_id     BIGINT,                     -- FK منطقی به fund_portfolio_reports
            period_end_date DATE NOT NULL,
            holding_type  VARCHAR(30) NOT NULL,       -- equity|fixed_income|deposit|gold|derivative|cash|other
            instrument_symbol  VARCHAR(50),
            instrument_name    VARCHAR(200),
            instrument_isin    VARCHAR(20),
            quantity      DOUBLE PRECISION,
            book_value    DOUBLE PRECISION,
            market_value  DOUBLE PRECISION,
            weight_pct    DOUBLE PRECISION,
            data_source   VARCHAR(30) NOT NULL DEFAULT 'api',
            payload_version SMALLINT NOT NULL DEFAULT 1,
            created_at    TIMESTAMP DEFAULT now(),
            updated_at    TIMESTAMP DEFAULT now(),
            CONSTRAINT uq_fund_holding UNIQUE (fund_id, period_end_date, holding_type, instrument_symbol)
        )
        """,
    ),
    # ── ۵. ردیابی ورود/خروج پول صندوق به نمادها (محاسباتی) ──
    (
        "fund_portfolio_diffs",
        """
        CREATE TABLE IF NOT EXISTS fund_portfolio_diffs (
            id            BIGSERIAL PRIMARY KEY,
            fund_id       VARCHAR(50) NOT NULL,
            instrument_symbol VARCHAR(50) NOT NULL,
            current_period_date  DATE NOT NULL,
            previous_period_date DATE,
            prev_weight_pct     DOUBLE PRECISION,
            curr_weight_pct     DOUBLE PRECISION,
            weight_change_pct   DOUBLE PRECISION,
            prev_market_value   DOUBLE PRECISION,
            curr_market_value   DOUBLE PRECISION,
            flow_direction      VARCHAR(10),   -- in | out | new | exited | hold
            computed_at  TIMESTAMP DEFAULT now(),
            CONSTRAINT uq_fund_diff UNIQUE (fund_id, current_period_date, instrument_symbol)
        )
        """,
    ),
    # ── ۶. کش قیمت‌های لحظه‌ای بازار صندوق‌ها ──
    (
        "fund_market_quotes_cache",
        """
        CREATE TABLE IF NOT EXISTS fund_market_quotes_cache (
            id            BIGSERIAL PRIMARY KEY,
            fund_id       VARCHAR(50) NOT NULL,
            symbol        VARCHAR(50),
            last_price    DOUBLE PRECISION,
            close_price   DOUBLE PRECISION,
            yesterday_price DOUBLE PRECISION,
            bid_price     DOUBLE PRECISION,
            ask_price     DOUBLE PRECISION,
            bid_volume    BIGINT,
            ask_volume    BIGINT,
            trade_volume  BIGINT,
            trade_value   DOUBLE PRECISION,
            market_value  DOUBLE PRECISION,
            price_change_pct DOUBLE PRECISION,
            quoted_at     TIMESTAMP NOT NULL,
            fetched_at    TIMESTAMP DEFAULT now(),
            CONSTRAINT uq_fund_quote UNIQUE (fund_id)
        )
        """,
    ),
    # ── ۷. تاریخچه امتیازدهی دوره‌ای ──
    (
        "fund_scores_history",
        """
        CREATE TABLE IF NOT EXISTS fund_scores_history (
            id            BIGSERIAL PRIMARY KEY,
            fund_id       VARCHAR(50) NOT NULL,
            score_date    DATE NOT NULL,
            total_score   DOUBLE PRECISION,
            return_score    DOUBLE PRECISION,
            risk_score      DOUBLE PRECISION,
            liquidity_score DOUBLE PRECISION,
            stability_score DOUBLE PRECISION,
            sharpe        DOUBLE PRECISION,
            sortino       DOUBLE PRECISION,
            max_drawdown  DOUBLE PRECISION,
            calmar        DOUBLE PRECISION,
            alpha         DOUBLE PRECISION,
            beta          DOUBLE PRECISION,
            rank_overall  INTEGER,
            rank_in_type  INTEGER,
            engine_version VARCHAR(20),
            payload_json  TEXT,
            created_at    TIMESTAMP DEFAULT now(),
            CONSTRAINT uq_fund_score UNIQUE (fund_id, score_date)
        )
        """,
    ),
    # ── ۸. قرنطینه داده‌های مخرب ──
    (
        "fund_ingestion_quarantine",
        """
        CREATE TABLE IF NOT EXISTS fund_ingestion_quarantine (
            id            BIGSERIAL PRIMARY KEY,
            source_endpoint VARCHAR(100),
            fund_id       VARCHAR(50),
            isin          VARCHAR(20),
            record_fingerprint VARCHAR(120),
            payload_json  TEXT,
            reject_reason VARCHAR(500) NOT NULL,
            reject_rule   VARCHAR(100),
            reviewed      BOOLEAN NOT NULL DEFAULT FALSE,
            created_at    TIMESTAMP DEFAULT now()
        )
        """,
    ),
]

_NEW_INDEXES: list[tuple[str, str]] = [
    ("ix_fund_nav_fund_date",     "CREATE INDEX IF NOT EXISTS ix_fund_nav_fund_date ON fund_nav_history (fund_id, nav_date DESC)"),
    ("ix_fund_nav_date",          "CREATE INDEX IF NOT EXISTS ix_fund_nav_date ON fund_nav_history (nav_date)"),
    ("ix_fund_reports_fund",      "CREATE INDEX IF NOT EXISTS ix_fund_reports_fund ON fund_portfolio_reports (fund_id, period_end_date DESC)"),
    ("ix_fund_holdings_fund",     "CREATE INDEX IF NOT EXISTS ix_fund_holdings_fund ON fund_holdings (fund_id, period_end_date DESC)"),
    ("ix_fund_holdings_symbol",   "CREATE INDEX IF NOT EXISTS ix_fund_holdings_symbol ON fund_holdings (instrument_symbol)"),
    ("ix_fund_diffs_fund",        "CREATE INDEX IF NOT EXISTS ix_fund_diffs_fund ON fund_portfolio_diffs (fund_id, current_period_date DESC)"),
    ("ix_fund_quotes_symbol",     "CREATE INDEX IF NOT EXISTS ix_fund_quotes_symbol ON fund_market_quotes_cache (symbol)"),
    ("ix_fund_quotes_quoted_at",  "CREATE INDEX IF NOT EXISTS ix_fund_quotes_quoted_at ON fund_market_quotes_cache (quoted_at DESC)"),
    ("ix_fund_scores_fund_date",  "CREATE INDEX IF NOT EXISTS ix_fund_scores_fund_date ON fund_scores_history (fund_id, score_date DESC)"),
    ("ix_fund_scores_rank",       "CREATE INDEX IF NOT EXISTS ix_fund_scores_rank ON fund_scores_history (score_date DESC, rank_overall)"),
    ("ix_fund_quarantine_review", "CREATE INDEX IF NOT EXISTS ix_fund_quarantine_review ON fund_ingestion_quarantine (reviewed, created_at DESC)"),
]


def upgrade() -> None:
    conn = op.get_bind()

    # ── ۱. ستون‌های افزایشی روی funds موجود (nullable / با default امن) ──
    existing_cols = {
        r[0] for r in conn.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = 'funds'")
        ).fetchall()
    }
    for col, ddl in _FUNDS_ADDITIVE_COLUMNS:
        if col in existing_cols:
            continue
        try:
            conn.execute(text(f"ALTER TABLE funds ADD COLUMN {col} {ddl}"))
        except Exception:
            # SQLite dev fallback: BOOLEAN DEFAULT etc. — keep additive-only guarantee
            conn.execute(text(f"ALTER TABLE funds ADD COLUMN {col} {ddl}"))

    # ISIN باید کلید کانونی قابل جستجو باشد (بدون unique enforcement تا داده‌های
    # موجود خالی مشکل‌ساز نشوند؛ فقط index)
    try:
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_funds_isin_lookup ON funds (isin)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_funds_national_id ON funds (national_id)"))
    except Exception:
        pass

    # ── ۲. جداول جدید ──
    for _name, ddl in _NEW_TABLES:
        conn.execute(text(ddl))

    # ── ۳. ایندکس‌ها ──
    for _name, ddl in _NEW_INDEXES:
        try:
            conn.execute(text(ddl))
        except Exception:
            pass  # already exists


def downgrade() -> None:
    # Additive-only: حذف فقط جداول جدید؛ ستون‌های funds برای احتیاط باقی می‌مانند.
    for _name, _ddl in reversed(_NEW_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {_name} CASCADE")
    for name, _ddl in reversed(_NEW_INDEXES):
        op.execute(f"DROP INDEX IF EXISTS {name}")
