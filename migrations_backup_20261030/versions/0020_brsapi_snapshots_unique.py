"""Add unique constraint on brsapi_symbol_snapshots (symbol, fetched_at).

Without this constraint the bulk-insert upsert (INSERT ... ON CONFLICT
DO NOTHING) never deduplicated rows — every 2-minute sync cycle appended
a fresh snapshot for every symbol, growing the table unboundedly and
making the DISTINCT ON (symbol) latest-wins queries (alert evaluation,
quote copying) unreliable.

Before adding the constraint we delete duplicate rows, keeping only the
newest row per (symbol, fetched_at), so the migration also succeeds on
already-populated databases.

Revision ID: 0020_brsapi_snapshots_unique
Revises: 0019_codal_attachments
"""
from __future__ import annotations

from alembic import op

revision = "0020_brsapi_snapshots_unique"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Delete duplicates, keeping the newest id per (symbol, fetched_at).
    op.execute(
        """
        DELETE FROM brsapi_symbol_snapshots a
        USING brsapi_symbol_snapshots b
        WHERE a.symbol = b.symbol
          AND a.fetched_at = b.fetched_at
          AND a.id < b.id
        """
    )
    with op.batch_alter_table("brsapi_symbol_snapshots") as batch_op:
        batch_op.create_unique_constraint(
            "uq_snap_symbol_fetched",
            ["symbol", "fetched_at"],
        )


def downgrade() -> None:
    with op.batch_alter_table("brsapi_symbol_snapshots") as batch_op:
        batch_op.drop_constraint("uq_snap_symbol_fetched", type_="unique")
