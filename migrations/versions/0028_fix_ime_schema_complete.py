"""Fix IME schema — add all missing columns to futures, options, certificates.

Migration 0025 only added a few specific columns. This migration
completes the job for ALL remaining missing columns across the
three IME tables that still throw ``UndefinedColumnError`` during sync.

Affected tables:
- brsapi_ime_futures   (missing orderbook bid_price + full ask side)
- brsapi_ime_options   (missing ~50 call/put + orderbook columns)
- brsapi_ime_certificates (missing date_y + full orderbook)
"""

from __future__ import annotations

import logging
from typing import Any

from alembic import op
from sqlalchemy import BigInteger, Float, Integer, String, Text
from sqlalchemy.engine import Connection

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.migration")

# ── Helpers ────────────────────────────────────────────


def _column_exists(conn: Connection, table: str, col: str) -> bool:
    """Return True if *col* already exists in *table*."""
    from sqlalchemy import text

    r = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c AND table_schema = 'public'"
        ),
        {"t": table, "c": col},
    )
    return r.scalar() is not None


def _add_column_if_missing(
    conn: Connection,
    table: str,
    col: str,
    col_type: Any,
    after: str | None = None,
) -> None:
    """Add a column if it doesn't already exist."""
    if _column_exists(conn, table, col):
        logger.info("  column %s.%s already exists — skipping", table, col)
        return
    after_clause = f' AFTER "{after}"' if after else ""
    op.execute(f'ALTER TABLE "{table}" ADD COLUMN "{col}" {col_type}{after_clause}')
    logger.info("  + column %s.%s (%s)", table, col, col_type)


def _drop_column_if_exists(conn: Connection, table: str, col: str) -> None:
    """Drop a column if it exists."""
    if _column_exists(conn, table, col):
        op.execute(f'ALTER TABLE "{table}" DROP COLUMN "{col}"')
        logger.info("  - column %s.%s dropped", table, col)


# ── Column type helpers ────────────────────────────────

def _t(typename: str, *args: Any) -> str:
    """Build a SQL type string like ``double precision`` or ``integer``."""
    if typename == "float":
        return "double precision"
    if typename == "int":
        return "integer"
    if typename == "bigint":
        return "bigint"
    if typename == "text":
        return "text"
    if typename == "varchar":
        return f"character varying({args[0]})" if args else "character varying(255)"
    return typename


# ── Upgrade ────────────────────────────────────────────


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. brsapi_ime_futures ──────────────────────────
    # Missing: bid_price_1..3, ask_volume_1..3, ask_price_1..3
    futures_orderbook = []
    for i in range(1, 4):
        futures_orderbook.append((f"bid_price_{i}", "float"))
    for i in range(1, 4):
        futures_orderbook.append((f"ask_volume_{i}", "int"))
    for i in range(1, 4):
        futures_orderbook.append((f"ask_price_{i}", "float"))

    logger.info("=== brsapi_ime_futures ===")
    for col_name, ctype in futures_orderbook:
        _add_column_if_missing(conn, "brsapi_ime_futures", col_name, _t(ctype))

    # ── 2. brsapi_ime_options ──────────────────────────
    # A LOT of call/put columns are missing.  List every column
    # that the ORM model declares.

    option_columns: list[tuple[str, str]] = [
        # Call fields
        ("call_contract_id", "bigint"),
        ("call_contract_code", "varchar(50)"),
        ("call_contract_description", "varchar(300)"),
        ("call_contract_size", "int"),
        ("call_contract_size_unit", "varchar(50)"),
        ("call_contract_currency", "varchar(10)"),
        ("call_date_end", "varchar(20)"),
        ("call_days_remaining", "int"),
        ("call_margin_initial", "float"),
        ("call_margin_required", "float"),
        ("call_open_interest", "int"),
        ("call_open_interest_change", "int"),
        ("call_open_interest_change_pct", "float"),
        ("call_price_yesterday", "float"),
        ("call_price_first", "float"),
        ("call_price_first_change", "float"),
        ("call_price_first_change_pct", "float"),
        ("call_price_max", "float"),
        ("call_price_max_change", "float"),
        ("call_price_max_change_pct", "float"),
        ("call_price_min", "float"),
        ("call_price_min_change", "float"),
        ("call_price_min_change_pct", "float"),
        ("call_price_last", "float"),
        ("call_price_last_change", "float"),
        ("call_price_last_change_pct", "float"),
        ("call_trade_count", "int"),
        ("call_trade_volume", "int"),
        ("call_trade_value", "float"),
        ("call_trade_value_unit", "varchar(20)"),
        # Put fields
        ("put_contract_id", "bigint"),
        ("put_contract_code", "varchar(50)"),
        ("put_contract_description", "varchar(300)"),
        ("put_contract_size", "int"),
        ("put_contract_size_unit", "varchar(50)"),
        ("put_contract_currency", "varchar(10)"),
        ("put_date_end", "varchar(20)"),
        ("put_days_remaining", "int"),
        ("put_margin_initial", "float"),
        ("put_margin_required", "float"),
        ("put_open_interest", "int"),
        ("put_open_interest_change", "int"),
        ("put_open_interest_change_pct", "float"),
        ("put_price_yesterday", "float"),
        ("put_price_first", "float"),
        ("put_price_first_change", "float"),
        ("put_price_first_change_pct", "float"),
        ("put_price_max", "float"),
        ("put_price_max_change", "float"),
        ("put_price_max_change_pct", "float"),
        ("put_price_min", "float"),
        ("put_price_min_change", "float"),
        ("put_price_min_change_pct", "float"),
        ("put_price_last", "float"),
        ("put_price_last_change", "float"),
        ("put_price_last_change_pct", "float"),
        ("put_trade_count", "int"),
        ("put_trade_volume", "int"),
        ("put_trade_value", "float"),
        ("put_trade_value_unit", "varchar(20)"),
        # Call orderbook (3 levels bid/ask)
        ("call_bid_volume_1", "int"),
        ("call_bid_price_1", "float"),
        ("call_bid_volume_2", "int"),
        ("call_bid_price_2", "float"),
        ("call_bid_volume_3", "int"),
        ("call_bid_price_3", "float"),
        ("call_ask_volume_1", "int"),
        ("call_ask_price_1", "float"),
        ("call_ask_volume_2", "int"),
        ("call_ask_price_2", "float"),
        ("call_ask_volume_3", "int"),
        ("call_ask_price_3", "float"),
        # Put orderbook (3 levels bid/ask)
        ("put_bid_volume_1", "int"),
        ("put_bid_price_1", "float"),
        ("put_bid_volume_2", "int"),
        ("put_bid_price_2", "float"),
        ("put_bid_volume_3", "int"),
        ("put_bid_price_3", "float"),
        ("put_ask_volume_1", "int"),
        ("put_ask_price_1", "float"),
        ("put_ask_volume_2", "int"),
        ("put_ask_price_2", "float"),
        ("put_ask_volume_3", "int"),
        ("put_ask_price_3", "float"),
    ]

    logger.info("=== brsapi_ime_options ===")
    for col_name, ctype in option_columns:
        _add_column_if_missing(conn, "brsapi_ime_options", col_name, _t(ctype))

    # Create missing indexes for options
    from sqlalchemy import text

    idx_list = conn.execute(
        text("SELECT indexname FROM pg_indexes WHERE tablename = 'brsapi_ime_options'")
    ).fetchall()
    existing_indexes = {r[0] for r in idx_list}

    if "idx_ime_option_call_code" not in existing_indexes:
        op.execute(
            "CREATE INDEX idx_ime_option_call_code ON brsapi_ime_options (call_contract_code)"
        )
        logger.info("  + index idx_ime_option_call_code")
    if "idx_ime_option_put_code" not in existing_indexes:
        op.execute(
            "CREATE INDEX idx_ime_option_put_code ON brsapi_ime_options (put_contract_code)"
        )
        logger.info("  + index idx_ime_option_put_code")

    # ── 3. brsapi_ime_certificates ─────────────────────
    # Missing: date_y + full orderbook (bid/ask 3 levels)

    certificate_columns: list[tuple[str, str]] = [
        ("date_y", "varchar(20)"),
        ("bid_volume_1", "int"),
        ("bid_price_1", "float"),
        ("bid_volume_2", "int"),
        ("bid_price_2", "float"),
        ("bid_volume_3", "int"),
        ("bid_price_3", "float"),
        ("ask_volume_1", "int"),
        ("ask_price_1", "float"),
        ("ask_volume_2", "int"),
        ("ask_price_2", "float"),
        ("ask_volume_3", "int"),
        ("ask_price_3", "float"),
    ]

    logger.info("=== brsapi_ime_certificates ===")
    for col_name, ctype in certificate_columns:
        _add_column_if_missing(conn, "brsapi_ime_certificates", col_name, _t(ctype))


# ── Downgrade ──────────────────────────────────────────


def downgrade() -> None:
    conn = op.get_bind()

    # Futures — drop added columns
    for i in range(1, 4):
        for prefix in ("bid_price_",):
            _drop_column_if_exists(conn, "brsapi_ime_futures", f"{prefix}{i}")
    for i in range(1, 4):
        for prefix in ("ask_volume_", "ask_price_"):
            _drop_column_if_exists(conn, "brsapi_ime_futures", f"{prefix}{i}")

    # Options — drop all columns that were NEWLY added by this migration.
    # Columns that already existed before 0028 (e.g. call_price_last_change_pct,
    # put_price_last_change_pct) are NOT included to avoid data-loss.
    option_downgrade_cols = [
        # Call fields new in 0028
        "call_contract_size_unit", "call_contract_currency",
        "call_open_interest_change", "call_open_interest_change_pct",
        "call_price_first",
        "call_price_first_change", "call_price_first_change_pct",
        "call_price_max_change", "call_price_max_change_pct",
        "call_price_min_change", "call_price_min_change_pct",
        "call_price_last_change",
        "call_trade_value_unit",
        # Put fields new in 0028
        "put_contract_size_unit", "put_contract_currency",
        "put_open_interest_change", "put_open_interest_change_pct",
        "put_price_first",
        "put_price_first_change", "put_price_first_change_pct",
        "put_price_max", "put_price_max_change", "put_price_max_change_pct",
        "put_price_min", "put_price_min_change", "put_price_min_change_pct",
        "put_price_last_change",
        "put_trade_value_unit",
    ]
    # Add all orderbook columns
    for side in ("call", "put"):
        for level in range(1, 4):
            for prefix in ("bid_volume_", "bid_price_", "ask_volume_", "ask_price_"):
                option_downgrade_cols.append(f"{side}_{prefix}{level}")

    for col in option_downgrade_cols:
        _drop_column_if_exists(conn, "brsapi_ime_options", col)

    # Drop option indexes
    from sqlalchemy import text

    idx_list = conn.execute(
        text("SELECT indexname FROM pg_indexes WHERE tablename = 'brsapi_ime_options'")
    ).fetchall()
    existing_indexes = {r[0] for r in idx_list}
    for idx_name in ("idx_ime_option_call_code", "idx_ime_option_put_code"):
        if idx_name in existing_indexes:
            op.execute(f"DROP INDEX IF EXISTS {idx_name}")
            logger.info("  - index %s dropped", idx_name)

    # Certificates — drop added columns
    cert_cols = ["date_y"]
    for i in range(1, 4):
        for prefix in ("bid_volume_", "bid_price_", "ask_volume_", "ask_price_"):
            cert_cols.append(f"{prefix}{i}")
    for col in cert_cols:
        _drop_column_if_exists(conn, "brsapi_ime_certificates", col)
