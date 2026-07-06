"""
BrsApi — Add Instrument Relations
===================================

Migration version: 0023
Revision ID:      0023
Revises:          0022

Adds ``instrument_id`` (FK → ``instruments.id``) and ``ins_id``
(TSETMC internal ID) columns to all BrsApi data tables that are
missing them.

Also adds a helper function to populate ``instrument_id`` from the
``instruments`` table by matching on ``symbol``.
"""

from __future__ import annotations

import logging
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | None = None
depends_on: str | None = None

logger = logging.getLogger("alembic.runtime.migration")

# ── Table definitions ────────────────────────────────────
# Each entry: (table_name, has_ins_id, has_instrument_id, pk_column)

TABLES: list[tuple[str, bool, bool, str]] = [
    # TSETMC tables
    ("brsapi_symbol_snapshots",   True,  False, "id"),
    ("brsapi_symbol_details",     True,  False, "ins_id"),
    ("brsapi_index_values",       False, False, "id"),
    ("brsapi_nav_records",        False, False, "id"),
    ("brsapi_option_snapshots",   True,  False, "id"),
    ("brsapi_intraday_trades",    False, False, "id"),
    ("brsapi_historical_daily",   False, False, "id"),
    ("brsapi_historical_real_legal", False, False, "id"),
    ("brsapi_candlesticks",       False, False, "id"),
    ("brsapi_shareholder_records", False, False, "id"),
    # IME tables
    ("brsapi_ime_futures",        False, False, "id"),
    ("brsapi_ime_options",        False, False, "id"),
    ("brsapi_ime_certificates",   False, False, "id"),
    ("brsapi_ime_funds",          True,  False, "id"),
    ("brsapi_ime_physical_trades", False, False, "id"),
    # Commodity / Crypto tables
    ("brsapi_commodity_prices",   False, False, "id"),
    ("brsapi_gold_coin_prices",   False, False, "id"),
    ("brsapi_gold_coin_history",  False, False, "id"),
    ("brsapi_currency_prices",    False, False, "id"),
    ("brsapi_currency_24h",       False, False, "id"),
    ("brsapi_gold_24h",           False, False, "id"),
    ("brsapi_crypto_prices",      False, False, "id"),
    # Codal
    ("brsapi_codal_announcements", False, False, "id"),
]


def _table_exists(table: str) -> bool:
    """Check if the table exists in the current database."""
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        result = bind.execute(
            sa.text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = :table"
            ),
            {"table": table},
        )
        return result.first() is not None
    # Fallback: try a simple SELECT
    try:
        bind.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 0"))
        return True
    except Exception:
        return False


def _add_columns(table: str, has_ins_id: bool, has_instrument_id: bool) -> None:
    """Add missing columns to a single table."""

    if not has_ins_id:
        op.add_column(
            table,
            sa.Column(
                "ins_id",
                sa.String(50),
                nullable=True,
                comment="TSETMC internal instrument ID",
            ),
        )

    if not has_instrument_id:
        op.add_column(
            table,
            sa.Column(
                "instrument_id",
                sa.String(50),
                nullable=True,
                comment="Foreign key to instruments.id",
            ),
        )


def _create_indexes(table: str, has_ins_id: bool, has_instrument_id: bool) -> None:
    """Create indexes for the new columns if they were added."""
    if not has_ins_id:
        try:
            op.create_index(
                f"idx_{table}_mig_ins_id",
                table,
                ["ins_id"],
            )
        except Exception:
            pass  # index may already exist
    if not has_instrument_id:
        try:
            op.create_index(
                f"idx_{table}_mig_instr",
                table,
                ["instrument_id"],
            )
        except Exception:
            pass  # index may already exist


def _fk_exists(table: str) -> bool:
    """Check if the FK constraint already exists on this table."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        result = bind.execute(
            sa.text(
                "SELECT 1 FROM information_schema.table_constraints "
                "WHERE constraint_type = 'FOREIGN KEY' "
                "AND table_name = :table "
                "AND constraint_name = :fk_name"
            ),
            {"table": table, "fk_name": f"fk_{table}_instrument"},
        )
        return result.first() is not None
    return False


def _create_fk_constraint(table: str) -> None:
    """Create FK constraint on instrument_id -> instruments.id."""
    if _fk_exists(table):
        return
    try:
        op.create_foreign_key(
            f"fk_{table}_instrument",
            table,
            "instruments",
            ["instrument_id"],
            ["id"],
            ondelete="SET NULL",
        )
    except Exception as exc:
        logger.warning("Could not create FK on %s: %s", table, exc)


def _populate_from_instruments(table: str) -> None:
    """
    Update ``instrument_id`` by matching ``symbol`` or ``ins_id`` against
    the ``instruments`` table.

    Skips tables that don't have a ``symbol`` column (e.g. index values).
    """
    if not _has_column(table, "symbol"):
        logger.info("Skipping instrument_id population for %s (no symbol column)", table)
        return

    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == "postgresql":
        op.execute(f"""
            UPDATE {table} AS t
            SET instrument_id = i.id
            FROM instruments AS i
            WHERE t.instrument_id IS NULL
              AND (
                (t.symbol IS NOT NULL AND t.symbol != '' AND t.symbol = i.symbol)
                OR
                (t.ins_id IS NOT NULL AND t.ins_id != '' AND t.ins_id = i.id)
              )
        """)
    else:
        op.execute(f"""
            UPDATE {table}
            SET instrument_id = (
                SELECT COALESCE(
                    (SELECT id FROM instruments WHERE symbol = {table}.symbol LIMIT 1),
                    (SELECT id FROM instruments WHERE id = {table}.ins_id LIMIT 1)
                )
            )
            WHERE instrument_id IS NULL
              AND (
                (symbol IS NOT NULL AND symbol != '')
                OR
                (ins_id IS NOT NULL AND ins_id != '')
              )
        """)


def _has_column(table: str, column: str) -> bool:
    """Check if the table has a specific column."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        result = bind.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :table AND column_name = :column"
            ),
            {"table": table, "column": column},
        )
        return result.first() is not None
    return True  # Assume column exists for non-PostgreSQL dialects


def _populate_ins_id_from_symbol(table: str) -> None:
    """
    Copy ``ins_id`` from ``brsapi_symbol_snapshots`` or
    ``brsapi_symbol_details`` where the symbol matches, for tables
    that don't have their own ``ins_id`` yet.

    Only runs if the table has a ``symbol`` column.
    """
    if not _has_column(table, "symbol"):
        logger.info("Skipping ins_id population for %s (no symbol column)", table)
        return

    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == "postgresql":
        op.execute(f"""
            UPDATE {table} AS t
            SET ins_id = COALESCE(
                (SELECT s.ins_id FROM brsapi_symbol_snapshots s
                 WHERE s.symbol = t.symbol LIMIT 1),
                (SELECT d.ins_id FROM brsapi_symbol_details d
                 WHERE d.symbol = t.symbol LIMIT 1)
            )
            WHERE t.symbol IS NOT NULL
              AND t.symbol != ''
              AND t.ins_id IS NULL
        """)
    else:
        op.execute(f"""
            UPDATE {table}
            SET ins_id = (
                SELECT ins_id FROM brsapi_symbol_snapshots
                WHERE brsapi_symbol_snapshots.symbol = {table}.symbol
                LIMIT 1
            )
            WHERE symbol IS NOT NULL
              AND symbol != ''
              AND ins_id IS NULL
        """)


def _drop_indexes(table: str, has_ins_id: bool, has_instrument_id: bool) -> None:
    """Drop indexes that were added."""
    if not has_ins_id:
        try:
            op.drop_index(f"idx_{table}_mig_ins_id", table_name=table)
        except Exception:
            pass
    if not has_instrument_id:
        try:
            op.drop_index(f"idx_{table}_mig_instr", table_name=table)
        except Exception:
            pass


def _drop_columns(table: str, has_ins_id: bool, has_instrument_id: bool) -> None:
    """Remove columns that were added."""
    if not has_instrument_id:
        op.drop_column(table, "instrument_id")
    if not has_ins_id:
        op.drop_column(table, "ins_id")


# ─────── UPGRADE ──────────────────────────────────


def upgrade() -> None:
    # 0. Filter to tables that actually exist
    existing_tables = [(t, h, i, p) for t, h, i, p in TABLES if _table_exists(t)]
    missing_tables = [(t, h, i, p) for t, h, i, p in TABLES if not _table_exists(t)]

    if missing_tables:
        logger.warning(
            "Skipping %d non-existent table(s): %s. "
            "These tables are defined in ORM models but not yet created in DB.",
            len(missing_tables),
            ", ".join(t[0] for t in missing_tables),
        )

    if not existing_tables:
        logger.info("No BrsApi tables to migrate.")
        return

    # 1. Add columns
    for table, has_ins_id, has_instrument_id, _ in existing_tables:
        _add_columns(table, has_ins_id, has_instrument_id)

    # 2. Create indexes
    for table, has_ins_id, has_instrument_id, _ in existing_tables:
        _create_indexes(table, has_ins_id, has_instrument_id)

    # 3. Populate ins_id from matching symbol snapshots
    for table, has_ins_id, _, _ in existing_tables:
        if not has_ins_id:
            _populate_ins_id_from_symbol(table)

    # 4. Populate instrument_id from instruments table
    for table, _, _, _ in existing_tables:
        _populate_from_instruments(table)

    # 5. Create FK constraints
    for table, _, _, pk in existing_tables:
        if pk != "ins_id":  # Don't add FK on tables where ins_id is the PK
            _create_fk_constraint(table)


# ─────── DOWNGRADE ────────────────────────────────


def downgrade() -> None:
    for table, has_ins_id, has_instrument_id, pk in reversed(TABLES):
        if not _table_exists(table):
            continue
        # Drop FK constraints first
        if pk != "ins_id":
            try:
                op.drop_constraint(f"fk_{table}_instrument", table, type_="foreignkey")
            except Exception:
                pass

        # Drop indexes
        _drop_indexes(table, has_ins_id, has_instrument_id)

        # Drop columns
        _drop_columns(table, has_ins_id, has_instrument_id)
