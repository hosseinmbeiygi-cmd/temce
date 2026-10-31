"""Add created_at column to brsapi_sync_log.

The sync log table was missing the created_at timestamp that the
BrsApiSyncService expects when persisting sync operation records.

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-27
"""

from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: ClassVar[set[str] | None] = None
depends_on: ClassVar[set[str] | None] = None


def upgrade() -> None:
    op.add_column(
        "brsapi_sync_log",
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_brsapi_sync_log_created_at", "brsapi_sync_log", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_brsapi_sync_log_created_at", "brsapi_sync_log")
    op.drop_column("brsapi_sync_log", "created_at")
