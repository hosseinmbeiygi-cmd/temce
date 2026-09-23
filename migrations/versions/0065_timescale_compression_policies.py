"""timescale compression policies for the populated hypertables

Revision ID: 0065
Revises: 0064
Create Date: 2026-09-23

TimescaleDB 2.x stores a compression *configuration* (which column to segment
by, which to order by) separately from the *policy* that decides when a chunk
is old enough to compress. Before this revision the database had neither:
``timescaledb_information.compression_settings`` was empty for every
hypertable, so even the five that reported ``compression_enabled = true`` had
nothing to compress and ``add_compression_policy()`` alone would have failed.

Scope is limited to hypertables that actually hold rows and are not part of the
0034 legacy rename. The ``*_deprecated`` hypertables and ``orderbook_snapshots``
(0 rows) are deliberately left alone.

The hot BrsApi tables (``brsapi_historical_daily``, ``brsapi_candlesticks``,
``brsapi_intraday_trades``) are NOT hypertables and cannot be converted by this
migration: their time columns are ``VARCHAR(20)`` Jalali strings, which
TimescaleDB will not accept as a time dimension (0063 documents the same
constraint for ``trades``/``quotes``). Converting them needs a typed timestamp
column first, which is a separate piece of work.

``downgrade()`` removes the policies but cannot un-compress chunks that the
background job has already moved — that is what ``decompress_chunk()`` is for
and it is intentionally not run here.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None

# table -> (segmentby column, orderby clause)
_TARGETS: list[tuple[str, str, str]] = [
    ("daily_real_legal", "symbol_id", "trade_date DESC"),
    ("gold_currency_prices", "symbol", "time DESC"),
    ("shareholders", "symbol_id", "record_date DESC"),
    ("etf_nav", "symbol_id", "time DESC"),
    ("commodity_prices", "symbol", "time DESC"),
]

def _timescaledb_present(conn) -> bool:
    return conn.execute(
        sa.text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'")
    ).fetchone() is not None


def _is_hypertable(conn, table: str) -> bool:
    return conn.execute(
        sa.text(
            "SELECT 1 FROM timescaledb_information.hypertables "
            "WHERE hypertable_name = :t"
        ),
        {"t": table},
    ).fetchone() is not None


def _has_compression_columns(conn, table: str) -> bool:
    """True once segmentby/orderby are configured — do not re-ALTER then."""
    return conn.execute(
        sa.text(
            "SELECT 1 FROM timescaledb_information.compression_settings "
            "WHERE hypertable_name = :t"
        ),
        {"t": table},
    ).fetchone() is not None


def _has_compression_policy(conn, table: str) -> bool:
    return conn.execute(
        sa.text(
            "SELECT 1 FROM timescaledb_information.jobs "
            "WHERE proc_name = 'policy_compression' AND hypertable_name = :t"
        ),
        {"t": table},
    ).fetchone() is not None


def upgrade() -> None:
    conn = op.get_bind()
    if not _timescaledb_present(conn):
        print("  ! timescaledb not installed — skipping compression policies")
        return

    for table, segmentby, orderby in _TARGETS:
        if not _is_hypertable(conn, table):
            print(f"  - {table}: not a hypertable, skipped")
            continue

        # A hypertable must have at least one row-bearing chunk to compress;
        # configuring columns on one is still valid, so no row-count gate here.
        if not _has_compression_columns(conn, table):
            conn.execute(sa.text(
                f'ALTER TABLE "{table}" SET ('
                f"timescaledb.compress, "
                f"timescaledb.compress_segmentby = '{segmentby}', "
                f"timescaledb.compress_orderby = '{orderby}'"
                f")"
            ))
            print(f"  + {table}: compression configured "
                  f"(segmentby={segmentby}, orderby={orderby})")
        else:
            print(f"  = {table}: compression columns already configured, left as is")

        if _has_compression_policy(conn, table):
            print(f"  = {table}: policy already exists")
            continue

        conn.execute(
            sa.text(
                "SELECT add_compression_policy(:t, INTERVAL '30 days', "
                "if_not_exists => TRUE)"
            ),
            {"t": table},
        )
        print(f"  + {table}: 30-day compression policy added")


def downgrade() -> None:
    conn = op.get_bind()
    if not _timescaledb_present(conn):
        return

    for table, _segmentby, _orderby in reversed(_TARGETS):
        if not _is_hypertable(conn, table):
            continue
        if _has_compression_policy(conn, table):
            conn.execute(
                sa.text("SELECT remove_compression_policy(:t, if_exists => TRUE)"),
                {"t": table},
            )
            print(f"  - {table}: compression policy removed")
