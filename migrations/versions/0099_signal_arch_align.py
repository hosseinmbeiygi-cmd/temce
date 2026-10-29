"""Alembic-style migration: extend signals + create data_freshness/data_quality_log/data_gaps."""
revision = "0099"
down_revision = "0066"
import contextlib

import sqlalchemy as sa
from alembic import op


def upgrade():
    for col in ["market","model_version","status"]:
        with contextlib.suppress(Exception):
            op.add_column("signals", sa.Column(col, sa.String(64)))
    for col in ["entry","stop_loss","take_profit","confidence","actual_outcome_price","actual_return_pct"]:
        with contextlib.suppress(Exception):
            op.add_column("signals", sa.Column(col, sa.Float()))
    for col in ["top_reasons","backtest_stats"]:
        with contextlib.suppress(Exception):
            op.add_column("signals", sa.Column(col, sa.Text()))
    with contextlib.suppress(Exception):
        op.add_column("signals", sa.Column("eval_due_at", sa.DateTime()))
    with contextlib.suppress(Exception):
        op.add_column("signals", sa.Column("checked_at", sa.DateTime()))
    with contextlib.suppress(Exception):
        op.add_column("signals", sa.Column("schema_version", sa.Integer(), server_default="1"))
    with contextlib.suppress(Exception):
        op.add_column("signals", sa.Column("was_correct", sa.Boolean()))
    op.create_table("data_freshness", sa.Column("data_type",sa.String(50),primary_key=True),
        sa.Column("last_ok",sa.DateTime()), sa.Column("ttl",sa.Integer(),server_default="300"))
    op.create_table("data_quality_log", sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("symbol",sa.String(50)), sa.Column("reason",sa.Text()))
    op.create_table("data_gaps", sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("symbol",sa.String(50),index=True), sa.Column("start",sa.DateTime()),
        sa.Column("end",sa.DateTime()), sa.Column("reason",sa.String(100)))
def downgrade(): pass
