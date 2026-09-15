"""M1: ml artifact provenance (hash, size, python version).

Revision ID: 0050
Revises: 0049
Create Date: 2026-09-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0050"
down_revision: str | None = "0049"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    for tbl in ("ml_model_versions", "ml_artifacts"):
        try:
            op.add_column(tbl, sa.Column("artifact_hash", sa.String(64), nullable=True))
            op.add_column(tbl, sa.Column("file_size_bytes", sa.BigInteger(), nullable=True))
            op.add_column(tbl, sa.Column("dataset_hash", sa.String(64), nullable=True))
        except Exception:
            # Table may not exist (ml_artifacts is file-only)
            pass
    try:
        op.create_index("ix_ml_model_versions_hash", "ml_model_versions", ["artifact_hash"])
    except Exception:
        pass


def downgrade() -> None:
    for tbl in ("ml_model_versions", "ml_artifacts"):
        try:
            op.drop_column(tbl, "artifact_hash")
            op.drop_column(tbl, "file_size_bytes")
            op.drop_column(tbl, "dataset_hash")
        except Exception:
            pass
    try:
        op.drop_index("ix_ml_model_versions_hash", table_name="ml_model_versions")
    except Exception:
        pass
