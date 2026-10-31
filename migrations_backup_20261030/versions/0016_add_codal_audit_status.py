"""Add audit_status column to brsapi_codal_announcements.

Stores the audit status extracted from the Codal announcement title,
e.g. "audited" or "unaudited".

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-27
"""

from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: ClassVar[set[str] | None] = None
depends_on: ClassVar[set[str] | None] = None


def upgrade() -> None:
    op.add_column(
        "brsapi_codal_announcements",
        sa.Column("audit_status", sa.String(20), nullable=True, comment="audited | unaudited"),
    )


def downgrade() -> None:
    op.drop_column("brsapi_codal_announcements", "audit_status")
