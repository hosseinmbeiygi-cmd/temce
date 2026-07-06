"""Add unique constraint on symbol column in instruments table

- instruments.symbol already has an index, adding UNIQUE constraint
- isin already has UNIQUE constraint from original migration

Revision ID: 0026
Revises: 0025
"""

from __future__ import annotations

from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove the non-unique index first, then create unique index
    op.drop_index("ix_instruments_symbol", table_name="instruments")
    op.create_index("ix_instruments_symbol", "instruments", ["symbol"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_instruments_symbol", table_name="instruments")
    op.create_index("ix_instruments_symbol", "instruments", ["symbol"])
