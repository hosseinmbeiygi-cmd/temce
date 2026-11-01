"""SIL-01 — bring the `brsapi_*` tables in line with the ORM.

A database created with ``alembic upgrade head`` from the 0004b baseline is
missing:

* ``ins_id`` / ``instrument_id`` on every table that uses
  ``InstrumentRefMixin`` (27 models) — every read of those tables fails with
  ``UndefinedColumnError`` even when the table is empty;
* the 3-level bid/ask order book on ``brsapi_ime_futures``;
* the three ``brsapi_gold_currency_pro_*`` tables entirely.

This migration is additive and idempotent (``IF NOT EXISTS``) so it is safe on
both the fresh baseline database and the legacy operational database.

Revision ID: 0121_brsapi_instrument_ref
Revises: 0120
"""

from __future__ import annotations

from alembic import op

revision = "0121_brsapi_instrument_ref"
down_revision = "0120"
branch_labels = None
depends_on = None

# Every BrsApiBase model that inherits InstrumentRefMixin (brsapi/models/*).
INSTRUMENT_REF_TABLES = (
    "brsapi_candlesticks",
    "brsapi_codal_announcements",
    "brsapi_commodity_prices",
    "brsapi_crypto_daily_history",
    "brsapi_crypto_prices",
    "brsapi_currency_24h",
    "brsapi_currency_prices",
    "brsapi_gold_24h",
    "brsapi_gold_coin_history",
    "brsapi_gold_coin_prices",
    "brsapi_gold_currency_pro_daily_history",
    "brsapi_gold_currency_pro_history_24h",
    "brsapi_gold_currency_pro_prices",
    "brsapi_historical_daily",
    "brsapi_historical_real_legal",
    "brsapi_ime_certificates",
    "brsapi_ime_funds",
    "brsapi_ime_futures",
    "brsapi_ime_options",
    "brsapi_ime_physical_trades",
    "brsapi_index_values",
    "brsapi_intraday_trades",
    "brsapi_nav_records",
    "brsapi_option_snapshots",
    "brsapi_shareholder_records",
    "brsapi_symbol_details",
    "brsapi_symbol_snapshots",
)

ORDERBOOK_COLUMNS = (
    ("bid_volume_1", "INTEGER"),
    ("bid_price_1", "FLOAT"),
    ("bid_volume_2", "INTEGER"),
    ("bid_price_2", "FLOAT"),
    ("bid_volume_3", "INTEGER"),
    ("bid_price_3", "FLOAT"),
    ("ask_volume_1", "INTEGER"),
    ("ask_price_1", "FLOAT"),
    ("ask_volume_2", "INTEGER"),
    ("ask_price_2", "FLOAT"),
    ("ask_volume_3", "INTEGER"),
    ("ask_price_3", "FLOAT"),
)

PRO_TABLES = {
    "brsapi_gold_currency_pro_prices": """
        CREATE TABLE IF NOT EXISTS brsapi_gold_currency_pro_prices (
            id BIGSERIAL PRIMARY KEY,
            ins_id VARCHAR(50),
            instrument_id VARCHAR(50),
            section VARCHAR(20) NOT NULL,
            symbol VARCHAR(30) NOT NULL,
            name_en VARCHAR(100),
            name VARCHAR(100),
            sign VARCHAR(10),
            price FLOAT,
            change_value FLOAT,
            change_percent FLOAT,
            unit VARCHAR(20) DEFAULT 'IRR',
            url_base_icon VARCHAR(300),
            path_icon VARCHAR(100),
            date VARCHAR(20),
            time VARCHAR(20),
            time_unix BIGINT,
            fetched_at VARCHAR(30),
            raw_json TEXT,
            created_at TIMESTAMP DEFAULT now()
        )
    """,
    "brsapi_gold_currency_pro_history_24h": """
        CREATE TABLE IF NOT EXISTS brsapi_gold_currency_pro_history_24h (
            id BIGSERIAL PRIMARY KEY,
            ins_id VARCHAR(50),
            instrument_id VARCHAR(50),
            symbol VARCHAR(30) NOT NULL,
            price FLOAT,
            time VARCHAR(20),
            date VARCHAR(20),
            time_unix BIGINT,
            fetched_at VARCHAR(30),
            raw_json TEXT,
            created_at TIMESTAMP DEFAULT now()
        )
    """,
    "brsapi_gold_currency_pro_daily_history": """
        CREATE TABLE IF NOT EXISTS brsapi_gold_currency_pro_daily_history (
            id BIGSERIAL PRIMARY KEY,
            ins_id VARCHAR(50),
            instrument_id VARCHAR(50),
            symbol VARCHAR(30) NOT NULL,
            name VARCHAR(100),
            sign VARCHAR(10),
            unit VARCHAR(20) DEFAULT 'IRR',
            url_base_icon VARCHAR(300),
            path_icon VARCHAR(100),
            date VARCHAR(20) NOT NULL,
            price_open FLOAT,
            price_high FLOAT,
            price_low FLOAT,
            price_close FLOAT,
            fetched_at VARCHAR(30),
            raw_json TEXT,
            created_at TIMESTAMP DEFAULT now()
        )
    """,
}

PRO_INDEXES = (
    ("idx_pro_price_section_symbol", "brsapi_gold_currency_pro_prices", "section, symbol"),
    ("idx_pro_price_fetched", "brsapi_gold_currency_pro_prices", "fetched_at"),
    ("idx_pro_24h_symbol_date", "brsapi_gold_currency_pro_history_24h", "symbol, date"),
    ("idx_pro_24h_fetched", "brsapi_gold_currency_pro_history_24h", "fetched_at"),
    ("idx_pro_daily_symbol_date", "brsapi_gold_currency_pro_daily_history", "symbol, date"),
    ("idx_pro_daily_fetched", "brsapi_gold_currency_pro_daily_history", "fetched_at"),
)


def upgrade() -> None:
    for ddl in PRO_TABLES.values():
        op.execute(ddl)

    for index_name, table, columns in PRO_INDEXES:
        op.execute(f'CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({columns})')

    for table in INSTRUMENT_REF_TABLES:
        op.execute(
            f'ALTER TABLE IF EXISTS {table} ADD COLUMN IF NOT EXISTS ins_id VARCHAR(50)'
        )
        op.execute(
            f'ALTER TABLE IF EXISTS {table} ADD COLUMN IF NOT EXISTS instrument_id VARCHAR(50)'
        )
        op.execute(
            f"CREATE INDEX IF NOT EXISTS ix_{table}_ins_id ON {table} (ins_id)"
        )
        op.execute(
            f"CREATE INDEX IF NOT EXISTS ix_{table}_instrument_id ON {table} (instrument_id)"
        )

    for column, sql_type in ORDERBOOK_COLUMNS:
        op.execute(
            f"ALTER TABLE IF EXISTS brsapi_ime_futures "
            f"ADD COLUMN IF NOT EXISTS {column} {sql_type}"
        )


def downgrade() -> None:
    # Additive-only migration: columns/tables may hold real provider data in an
    # operational database, so the downgrade intentionally does not drop them.
    pass
