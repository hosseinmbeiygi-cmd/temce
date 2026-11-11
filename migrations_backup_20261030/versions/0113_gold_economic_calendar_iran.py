"""Gold economic calendar + Iran manual events (2 tables).

Revision ID: 0113
Revises: 0112
Create Date: 2026-10-18

Table gold_economic_calendar_events: CPI / NFP / FOMC high-volatility calendar
events with an ``is_high_volatility`` flag and ``fetched_at`` per row.
Table gold_iran_manual_events: Iran-specific manual-entry calendar events
(operators only; no external feed).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0113"
down_revision = "0112"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gold_economic_calendar_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("event_date", sa.Date(), nullable=False, index=True),
        sa.Column("event_time", sa.String(length=16), nullable=True),
        sa.Column("title", sa.String(length=256), nullable=True),
        sa.Column("country", sa.String(length=32), nullable=True, index=True),
        sa.Column("category", sa.String(length=64), nullable=True, index=True),
        sa.Column("importance", sa.Integer(), server_default="2", nullable=True),
        sa.Column(
            "is_high_volatility",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=True,
        ),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "uq_gold_economic_calendar_event_id",
        "gold_economic_calendar_events",
        ["event_id"],
        unique=True,
    )

    op.create_table(
        "gold_iran_manual_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("event_date", sa.Date(), nullable=False, index=True),
        sa.Column("event_time", sa.String(length=16), nullable=True),
        sa.Column("title", sa.String(length=256), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("importance", sa.Integer(), server_default="2", nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "is_high_volatility",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "uq_gold_iran_manual_event_id",
        "gold_iran_manual_events",
        ["event_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_gold_iran_manual_event_id", table_name="gold_iran_manual_events")
    op.drop_table("gold_iran_manual_events")
    op.drop_index(
        "uq_gold_economic_calendar_event_id",
        table_name="gold_economic_calendar_events",
    )
    op.drop_table("gold_economic_calendar_events")
