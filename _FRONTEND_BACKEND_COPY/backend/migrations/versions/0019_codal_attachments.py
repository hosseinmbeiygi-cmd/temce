"""
Codal Attachments Table
=========================

Revision ID:      0019
Down Revision:    0018

Creates ``brsapi_codal_attachments`` to hold downloaded Codal
announcement files (PDF/Excel/attachments).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "brsapi_codal_attachments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("announcement_id", sa.BigInteger(), nullable=False),
        sa.Column("symbol", sa.String(50), nullable=True),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("attachment_type", sa.String(20), nullable=False, comment="pdf | excel | attachment | html | other"),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column(
            "storage_type", sa.String(20), nullable=False, server_default="local", comment="local | s3 | database"
        ),
        sa.Column("storage_path", sa.String(500), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            comment="pending | downloading | done | error",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(), nullable=True),
        sa.Column("content", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("announcement_id", "attachment_type", name="uq_codal_attachment"),
        sa.Index("idx_codal_attachment_status", "status", "created_at"),
        sa.Index("idx_codal_attachment_symbol", "symbol", "created_at"),
    )


def downgrade() -> None:
    op.drop_table("brsapi_codal_attachments")
