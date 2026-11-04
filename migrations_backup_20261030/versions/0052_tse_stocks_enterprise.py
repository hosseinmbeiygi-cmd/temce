"""TSE Stocks Enterprise Module — additive tables (Migration 0052).

Strictly Additive / Zero Breaking Changes:
  - ``stocks`` موجود دست‌نخورده می‌ماند؛ ستون‌های جدید فقط nullable.
  - جداول جدید برای میکرواستراکچر، اندیکاتورها، سیگنال کوانت و سنتیمنت.
  - کلید کانونی: ISIN (اولویت) + نماد.
  - جدول‌های سری‌زمانی با ایندکس ترکیبی (symbol, ts DESC) برای پاسخ < ۵۰ms.

Revision ID: 0052
Revises: 0051
"""

from __future__ import annotations

import contextlib

from alembic import op
from sqlalchemy import text

revision: str = "0052"
down_revision: str | None = "0051"
branch_labels: str | None = None
depends_on: str | None = None

_ADDITIVE_COLUMNS = [
    # (table, [(column, ddl), ...])
    ("symbols", [
        ("isin", "VARCHAR(20)"),
        ("market_segment", "VARCHAR(30)"),   # bourse1|bourse2|ifb1|ifb2|base_yellow|base_orange|base_red
        ("trading_state", "VARCHAR(30)"),    # allowed|forbidden|suspended|auction
        ("industry_name", "VARCHAR(100)"),
        ("base_volume", "BIGINT"),
        ("free_float_pct", "DOUBLE PRECISION"),
        ("price_range_pct", "DOUBLE PRECISION"),  # دامنه نوسان پویا 1|2|5
    ]),
]

_NEW_TABLES: list[tuple[str, str]] = [
    # ── اسنپ‌شات زنده تابلو (upsert روی symbol) ──
    (
        "stock_live_tape",
        """
        CREATE TABLE IF NOT EXISTS stock_live_tape (
            symbol          VARCHAR(50) PRIMARY KEY,
            isin            VARCHAR(20),
            last_price      DOUBLE PRECISION,
            close_price     DOUBLE PRECISION,
            yesterday_price DOUBLE PRECISION,
            price_first     DOUBLE PRECISION,
            price_min       DOUBLE PRECISION,
            price_max       DOUBLE PRECISION,
            price_change_pct     DOUBLE PRECISION,
            close_change_pct     DOUBLE PRECISION,
            trade_volume    BIGINT,
            trade_value     DOUBLE PRECISION,
            trade_count     BIGINT,
            buy_real_volume BIGINT,
            sell_real_volume BIGINT,
            buy_real_count  BIGINT,
            sell_real_count BIGINT,
            buy_real_value  DOUBLE PRECISION,
            sell_real_value DOUBLE PRECISION,
            buy_legal_volume BIGINT,
            sell_legal_volume BIGINT,
            buy_legal_value DOUBLE PRECISION,
            sell_legal_value DOUBLE PRECISION,
            buy_orders_json TEXT,
            sell_orders_json TEXT,
            base_volume     BIGINT,
            allowed_price_min DOUBLE PRECISION,
            allowed_price_max DOUBLE PRECISION,
            quoted_at       TIMESTAMP NOT NULL,
            fetched_at      TIMESTAMP DEFAULT now()
        )
        """,
    ),
    # ── اسنپ‌شات L2 دفتر سفارشات ۵ مظنه ──
    (
        "stock_order_book_l2",
        """
        CREATE TABLE IF NOT EXISTS stock_order_book_l2 (
            id          BIGSERIAL PRIMARY KEY,
            symbol      VARCHAR(50) NOT NULL,
            isin        VARCHAR(20),
            bids_json   TEXT NOT NULL,      -- [{level,price,volume,count}]
            asks_json   TEXT NOT NULL,
            obi_5       DOUBLE PRECISION,   -- Order Book Imbalance 5-level
            bid_queue_value DOUBLE PRECISION,
            ask_queue_value DOUBLE PRECISION,
            captured_at TIMESTAMP NOT NULL,
            CONSTRAINT uq_obl_symbol_ts UNIQUE (symbol, captured_at)
        )
        """,
    ),
    # ── اسنپ‌شات روزانه اندیکاتورها (precomputed overnight) ──
    (
        "stock_indicators_snapshot",
        """
        CREATE TABLE IF NOT EXISTS stock_indicators_snapshot (
            symbol      VARCHAR(50) NOT NULL,
            trade_date  DATE NOT NULL,
            rsi_14      DOUBLE PRECISION,
            rsi_divergence VARCHAR(10),     -- RD+|RD-|HD+|HD-|none
            macd        DOUBLE PRECISION,
            macd_signal DOUBLE PRECISION,
            macd_hist   DOUBLE PRECISION,
            ema_20      DOUBLE PRECISION,
            ema_50      DOUBLE PRECISION,
            ema_100     DOUBLE PRECISION,
            ema_200     DOUBLE PRECISION,
            ema_cross   VARCHAR(20),        -- golden|death|none
            bb_upper    DOUBLE PRECISION,
            bb_middle   DOUBLE PRECISION,
            bb_lower    DOUBLE PRECISION,
            bb_squeeze  BOOLEAN DEFAULT FALSE,
            keltner_upper DOUBLE PRECISION,
            keltner_lower DOUBLE PRECISION,
            ichimoku_tenkan DOUBLE PRECISION,
            ichimoku_kijun  DOUBLE PRECISION,
            ichimoku_senkou_a DOUBLE PRECISION,
            ichimoku_senkou_b DOUBLE PRECISION,
            ichimoku_state  VARCHAR(20),   -- above_kumo|inside_kumo|below_kumo
            atr_14      DOUBLE PRECISION,
            mfi_14      DOUBLE PRECISION,
            vwap_daily  DOUBLE PRECISION,
            pivot_standard_json TEXT,
            pivot_camarilla_json TEXT,
            pivot_fibonacci_json TEXT,
            trend_alignment_score DOUBLE PRECISION,  -- MTF alignment 0..100
            computed_at TIMESTAMP DEFAULT now(),
            CONSTRAINT uq_stock_ind UNIQUE (symbol, trade_date)
        )
        """,
    ),
    # ── سیگنال‌های کوانت (تاریخچه) ──
    (
        "stock_quant_signals",
        """
        CREATE TABLE IF NOT EXISTS stock_quant_signals (
            id          BIGSERIAL PRIMARY KEY,
            symbol      VARCHAR(50) NOT NULL,
            isin        VARCHAR(20),
            signal_date DATE NOT NULL,
            action      VARCHAR(20) NOT NULL,  -- strong_buy|accumulate|hold|reduce|sell
            composite_score DOUBLE PRECISION,
            tape_score    DOUBLE PRECISION,
            tech_score    DOUBLE PRECISION,
            fund_score    DOUBLE PRECISION,
            peer_score    DOUBLE PRECISION,
            macro_score   DOUBLE PRECISION,
            entry_low   DOUBLE PRECISION,
            entry_high  DOUBLE PRECISION,
            stop_loss   DOUBLE PRECISION,
            target_1    DOUBLE PRECISION,
            target_2    DOUBLE PRECISION,
            target_3    DOUBLE PRECISION,
            risk_reward DOUBLE PRECISION,
            kelly_fraction DOUBLE PRECISION,
            position_size_pct DOUBLE PRECISION,
            market_regime VARCHAR(20),   -- high_volume|eroding|falling
            reasons_pro   TEXT,
            reasons_con   TEXT,
            engine_version VARCHAR(20),
            payload_json  TEXT,
            created_at    TIMESTAMP DEFAULT now(),
            CONSTRAINT uq_stock_signal UNIQUE (symbol, signal_date)
        )
        """,
    ),
    # ── اخبار و سنتیمنت ──
    (
        "stock_news_sentiment",
        """
        CREATE TABLE IF NOT EXISTS stock_news_sentiment (
            id          BIGSERIAL PRIMARY KEY,
            symbol      VARCHAR(50),
            isin        VARCHAR(20),
            industry    VARCHAR(100),
            title       VARCHAR(500) NOT NULL,
            body        TEXT,
            source      VARCHAR(100),
            published_at TIMESTAMP,
            sentiment   VARCHAR(10),        -- positive|neutral|negative
            sentiment_score DOUBLE PRECISION, -- -1..+1
            impact_tag  VARCHAR(30),        -- halting|feed_rate|tax|dilution|sanction|fx
            created_at  TIMESTAMP DEFAULT now()
        )
        """,
    ),
    # ── فروش ماهانه کدال ──
    (
        "stock_monthly_sales_production",
        """
        CREATE TABLE IF NOT EXISTS stock_monthly_sales_production (
            id          BIGSERIAL PRIMARY KEY,
            symbol      VARCHAR(50) NOT NULL,
            isin        VARCHAR(20),
            jalali_year INTEGER NOT NULL,
            jalali_month INTEGER NOT NULL,
            product_name VARCHAR(200),
            sales_amount DOUBLE PRECISION,   -- ریال
            sales_volume DOUBLE PRECISION,   -- تناژ/مقدار
            unit_price  DOUBLE PRECISION,
            sales_mom_pct DOUBLE PRECISION,
            sales_yoy_pct DOUBLE PRECISION,
            is_all_time_high BOOLEAN DEFAULT FALSE,
            codal_letter_id VARCHAR(50),
            created_at  TIMESTAMP DEFAULT now(),
            CONSTRAINT uq_stock_monthly_sales UNIQUE (symbol, jalali_year, jalali_month, product_name)
        )
        """,
    ),
    # ── متغیرهای کلان بازار ──
    (
        "market_macro_indicators",
        """
        CREATE TABLE IF NOT EXISTS market_macro_indicators (
            id          BIGSERIAL PRIMARY KEY,
            indicator_date DATE NOT NULL,
            usd_nima    DOUBLE PRECISION,
            usd_free    DOUBLE PRECISION,
            usd_gap_pct DOUBLE PRECISION,
            interbank_rate DOUBLE PRECISION,
            akhzar_ytm  DOUBLE PRECISION,
            total_retail_value DOUBLE PRECISION,
            queue_buy_value  DOUBLE PRECISION,
            queue_sell_value DOUBLE PRECISION,
            market_regime VARCHAR(20),
            created_at  TIMESTAMP DEFAULT now(),
            CONSTRAINT uq_macro_date UNIQUE (indicator_date)
        )
        """,
    ),
]

_NEW_INDEXES: list[tuple[str, str]] = [
    ("ix_obl_symbol_captured", "CREATE INDEX IF NOT EXISTS ix_obl_symbol_captured ON stock_order_book_l2 (symbol, captured_at DESC)"),
    ("ix_obl_captured", "CREATE INDEX IF NOT EXISTS ix_obl_captured ON stock_order_book_l2 (captured_at DESC)"),
    ("ix_stockind_date", "CREATE INDEX IF NOT EXISTS ix_stockind_date ON stock_indicators_snapshot (trade_date DESC)"),
    ("ix_sig_symbol_date", "CREATE INDEX IF NOT EXISTS ix_sig_symbol_date ON stock_quant_signals (symbol, signal_date DESC)"),
    ("ix_sig_date_action", "CREATE INDEX IF NOT EXISTS ix_sig_date_action ON stock_quant_signals (signal_date DESC, action)"),
    ("ix_news_symbol_pub", "CREATE INDEX IF NOT EXISTS ix_news_symbol_pub ON stock_news_sentiment (symbol, published_at DESC)"),
    ("ix_news_sentiment", "CREATE INDEX IF NOT EXISTS ix_news_sentiment ON stock_news_sentiment (sentiment)"),
    ("ix_msales_symbol", "CREATE INDEX IF NOT EXISTS ix_msales_symbol ON stock_monthly_sales_production (symbol, jalali_year DESC, jalali_month DESC)"),
    ("ix_macro_date", "CREATE INDEX IF NOT EXISTS ix_macro_date ON market_macro_indicators (indicator_date DESC)"),
    ("ix_tape_quoted", "CREATE INDEX IF NOT EXISTS ix_tape_quoted ON stock_live_tape (quoted_at DESC)"),
]


def upgrade() -> None:
    conn = op.get_bind()

    # ستون‌های additive روی symbols
    existing = {
        r[0] for r in conn.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = 'symbols'")
        ).fetchall()
    }
    for _table, cols in _ADDITIVE_COLUMNS:
        for col, ddl in cols:
            if col in existing:
                continue
            with contextlib.suppress(Exception):
                conn.execute(text(f"ALTER TABLE symbols ADD COLUMN {col} {ddl}"))

    with contextlib.suppress(Exception):
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_symbols_isin ON symbols (isin)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_symbols_industry ON symbols (industry_name)"))

    for _name, ddl in _NEW_TABLES:
        conn.execute(text(ddl))

    for _name, ddl in _NEW_INDEXES:
        with contextlib.suppress(Exception):
            conn.execute(text(ddl))


def downgrade() -> None:
    for _name, _ddl in reversed(_NEW_INDEXES):
        op.execute(f"DROP INDEX IF EXISTS {_name}")
    for _name, _ddl in reversed(_NEW_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {_name} CASCADE")
