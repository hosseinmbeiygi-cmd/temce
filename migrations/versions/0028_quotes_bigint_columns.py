"""quotes: widen int32 columns to bigint (fixes overflow in bulk upserts)

Revision ID: 0028_quotes_bigint_columns
Revises: 0027_signal_engine_indexes
Create Date: 2026-08-07

The quotes table defines trade_count / ask_volume / bid_volume as INTEGER
(int32). Snapshot values (e.g. bid_volume = 3,084,690,654) exceed the int32
range, causing executemany() failures in jobs/definitions/sync_jobs.py and
the alert evaluation flow. Widening to BIGINT fixes it.
"""

from __future__ import annotations

import contextlib

import sqlalchemy as sa
from alembic import op

revision: str = "0028_quotes_bigint_columns"
down_revision: str | None = "0027_signal_engine_indexes"
branch_labels = None
depends_on = None

_QUOTES = "quotes"
_COLUMNS = ("trade_count", "ask_volume", "bid_volume")


def upgrade() -> None:
    bind = op.get_bind()
    # Check if the table is a TimescaleDB hypertable; if so, widen via
    # ALTER COLUMN TYPE (supported for hypertables) rather than table rewrite.
    is_hypertable = False
    try:
        row = bind.execute(
            sa.text(
                "SELECT hypertable_name FROM timescaledb_information.hypertables "
                "WHERE hypertable_name = :t"
            ),
            {"t": _QUOTES},
        ).first()
        is_hypertable = row is not None
    except Exception:
        pass

    for col in _COLUMNS:
        stmt = sa.text(
            f'ALTER TABLE "{_QUOTES}" ALTER COLUMN "{col}" TYPE BIGINT USING '
            f'CASE WHEN "{col}" IS NULL THEN NULL ELSE "{col}"::BIGINT END'
        )
        bind.execute(stmt)

    if is_hypertable:
        # Keep indexes valid after type change (hypertables don't auto-rebuild).
        with contextlib.suppress(Exception):
            bind.execute(
                sa.text(
                    'SELECT create_hypertable(:t, :col, if_not_exists := TRUE)'
                ),
                {"t": _QUOTES, "col": "time"},
            )


def downgrade() -> None:
    bind = op.get_bind()
    for col in _COLUMNS:
        bind.execute(
            sa.text(
                f'ALTER TABLE "{_QUOTES}" ALTER COLUMN "{col}" TYPE INTEGER USING '
                f'CASE WHEN "{col}" IS NULL THEN NULL '
                f'WHEN "{col}" > 2147483647 THEN 2147483647 '
                f'ELSE "{col}"::INTEGER END'
            )
        )
