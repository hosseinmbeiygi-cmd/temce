"""M1: ml artifact provenance (hash, size, python version).

Revision ID: 0050
Revises: 0049
Create Date: 2026-09-09

Fixed 2026-09-16: previous implementation wrapped ``op.add_column`` in
``try/except`` for optional tables. On PostgreSQL a failed statement aborts
the surrounding transaction, so the swallowed error poisoned every later
statement (``InFailedSQLTransactionError``) and the whole upgrade rolled
back. We now check ``information_schema`` first — no failing statement, no
aborted transaction, fully idempotent.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0050"
down_revision: str | None = "0049"
branch_labels: str | None = None
depends_on: str | None = None

_TABLES = ("ml_model_versions", "ml_artifacts")
_COLUMNS: tuple[tuple[str, sa.types.TypeEngine], ...] = (
    ("artifact_hash", sa.String(64)),
    ("file_size_bytes", sa.BigInteger()),
    ("dataset_hash", sa.String(64)),
)


def _existing_tables() -> set[str]:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = ANY(:names)"
        ),
        {"names": list(_TABLES)},
    )
    return {r[0] for r in rows}


def _existing_columns(table: str) -> set[str]:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :t"
        ),
        {"t": table},
    )
    return {r[0] for r in rows}


def upgrade() -> None:
    tables = _existing_tables()
    for tbl in _TABLES:
        if tbl not in tables:
            continue  # ml_artifacts may be file-only in some deployments
        cols = _existing_columns(tbl)
        for name, coltype in _COLUMNS:
            if name in cols:
                continue
            op.add_column(tbl, sa.Column(name, coltype, nullable=True))
    if "ml_model_versions" in tables:
        indexes = {
            r[0]
            for r in op.get_bind().execute(
                sa.text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE tablename = 'ml_model_versions'"
                )
            )
        }
        if "ix_ml_model_versions_hash" not in indexes:
            op.create_index(
                "ix_ml_model_versions_hash", "ml_model_versions", ["artifact_hash"]
            )


def downgrade() -> None:
    tables = _existing_tables()
    for tbl in _TABLES:
        if tbl not in tables:
            continue
        cols = _existing_columns(tbl)
        for name, _coltype in reversed(_COLUMNS):
            if name in cols:
                op.drop_column(tbl, name)
    if "ml_model_versions" in tables:
        indexes = {
            r[0]
            for r in op.get_bind().execute(
                sa.text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE tablename = 'ml_model_versions'"
                )
            )
        }
        if "ix_ml_model_versions_hash" in indexes:
            op.drop_index("ix_ml_model_versions_hash", table_name="ml_model_versions")
