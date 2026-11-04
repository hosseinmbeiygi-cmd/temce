"""Add ``shareholder_id`` to ``brsapi_shareholder_records``.

The ``Shareholder.php`` API returns a numeric ``id`` per shareholder (TSETMC's
internal shareholder id). The parser previously discarded it; this migration
adds a column so the id is stored and the table can be joined / deduped by
shareholder instead of by name.

Revision ID: 0033_add_shareholder_id
Revises: 0032_candlestick_dedup_indexes
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0033_add_shareholder_id"
down_revision = "0032_candlestick_dedup_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            "ALTER TABLE brsapi_shareholder_records "
            "ADD COLUMN IF NOT EXISTS shareholder_id BIGINT"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_brsapi_shareholder_records_shareholder_id "
            "ON brsapi_shareholder_records (shareholder_id)"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            "DROP INDEX IF EXISTS ix_brsapi_shareholder_records_shareholder_id"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE brsapi_shareholder_records "
            "DROP COLUMN IF EXISTS shareholder_id"
        )
    )
