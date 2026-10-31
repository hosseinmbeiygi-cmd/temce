"""add_codal_content_hash

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-27 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0018"
down_revision = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "brsapi_codal_announcements",
        sa.Column("content_hash", sa.String(64), nullable=True),
    )
    # Unique constraint also creates the index we need for lookups.
    op.create_unique_constraint(
        "uq_codal_content_hash",
        "brsapi_codal_announcements",
        ["content_hash"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_codal_content_hash", "brsapi_codal_announcements", type_="unique")
    op.drop_column("brsapi_codal_announcements", "content_hash")
