"""Alembic-style migration: extend signals + create data_freshness/data_quality_log/data_gaps."""
revision = "0099"
down_revision = "0066"

import sqlalchemy as sa
from alembic import op


def upgrade():
    # IF NOT EXISTS keeps this idempotent; a failed ADD COLUMN would abort the
    # migration transaction even when the exception is suppressed (DB-02, 2026-10-30).
    columns = [
        ("market", "VARCHAR(64)"),
        ("model_version", "VARCHAR(64)"),
        ("status", "VARCHAR(64)"),
        ("entry", "DOUBLE PRECISION"),
        ("stop_loss", "DOUBLE PRECISION"),
        ("take_profit", "DOUBLE PRECISION"),
        ("confidence", "DOUBLE PRECISION"),
        ("actual_outcome_price", "DOUBLE PRECISION"),
        ("actual_return_pct", "DOUBLE PRECISION"),
        ("top_reasons", "TEXT"),
        ("backtest_stats", "TEXT"),
        ("eval_due_at", "TIMESTAMP WITHOUT TIME ZONE"),
        ("checked_at", "TIMESTAMP WITHOUT TIME ZONE"),
        ("schema_version", "INTEGER DEFAULT 1"),
        ("was_correct", "BOOLEAN"),
    ]
    for col, col_type in columns:
        op.execute(
            f"ALTER TABLE IF EXISTS signals ADD COLUMN IF NOT EXISTS {col} {col_type}"
        )
    op.create_table("data_freshness", sa.Column("data_type",sa.String(50),primary_key=True),
        sa.Column("last_ok",sa.DateTime()), sa.Column("ttl",sa.Integer(),server_default="300"))
    op.create_table("data_quality_log", sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("symbol",sa.String(50)), sa.Column("reason",sa.Text()))
    op.create_table("data_gaps", sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("symbol",sa.String(50),index=True), sa.Column("start",sa.DateTime()),
        sa.Column("end",sa.DateTime()), sa.Column("reason",sa.String(100)))
def downgrade(): pass
