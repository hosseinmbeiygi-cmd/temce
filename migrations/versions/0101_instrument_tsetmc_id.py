"""Add instruments.tsetmc_id — stable TSETMC identity (audit DP-019)

Revision ID: 0101
Revises: 0100
Create Date: 2026-09-27

TSETMC instrument codes (``ins_code``) are the stable identity for a listed
instrument across symbol renames — and symbols on TSE rename often. The
``instruments`` table previously persisted only the mutable ``symbol``, so a
rename orphaned every symbol-keyed join. This migration adds a unique,
indexed ``tsetmc_id`` column. Additive only; the backfill derives values from
the snapshot table where possible.

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0101"
down_revision = "0100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = {c["name"] for c in inspector.get_columns("instruments")}

    if "tsetmc_id" not in columns:
        op.add_column("instruments", sa.Column("tsetmc_id", sa.String(50), nullable=True))

    # Unique index — created non-concurrently inside the transaction like
    # the other additive migrations in this chain. Duplicate TSETMC codes
    # would be a data error anyway.
    op.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_instruments_tsetmc_id "
        "ON instruments (tsetmc_id)"
    ))

    # Best-effort backfill from the snapshot table (latest snapshot wins).
    # Instruments without any snapshot keep NULL and are filled by the next
    # ingestion run.
    op.execute(sa.text("""
        UPDATE instruments i
        SET tsetmc_id = s.ins_id
        FROM (
            SELECT DISTINCT ON (symbol) symbol, ins_id
            FROM brsapi_symbol_snapshots
            WHERE ins_id IS NOT NULL
            ORDER BY symbol, id DESC
        ) s
        WHERE i.tsetmc_id IS NULL AND i.symbol = s.symbol
    """))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_instruments_tsetmc_id"))
    op.drop_column("instruments", "tsetmc_id")
