"""Sync log outcome column.

Revision ID: 0116
Revises: 0043_gold_holding_soft_delete
Create Date: 2026-10-29

``brsapi_sync_log.outcome`` records *why* a sync run ended the way it did
(``success``, ``empty``, ``malformed``, ``provider_blocked``, ``parse_error``,
``storage_error`` …). ``status`` alone could not distinguish "the provider
answered with nothing" from "we could not read the answer", which is how a
blocked source used to look like a healthy zero-row sync.

Existing rows default to ``unknown``: their true outcome was never recorded and
must not be guessed.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# ``0115`` is a branch point: 0043 (GoldDesk) already forked from it, so this
# migration extends the current head instead of opening a second head that would
# make ``alembic upgrade head`` abort with "multiple heads".
revision = "0116"
down_revision = "0043_gold_holding_soft_delete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "brsapi_sync_log",
        sa.Column(
            "outcome",
            sa.String(length=30),
            nullable=False,
            server_default="unknown",
        ),
    )


def downgrade() -> None:
    op.drop_column("brsapi_sync_log", "outcome")
