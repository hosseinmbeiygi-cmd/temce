"""0043 - Antigravity data collection layer.

Adds a source registry, canonical market ticks hypertable and an auditable
quality-event table.  Raw payloads remain in the configured object lake; the
time-series table stores only the content hash/object key.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0043"
down_revision = "0042_gold_portfolio"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_data_sources",
        sa.Column("source", sa.String(64), primary_key=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("asset_class", sa.String(32), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("poll_interval_seconds", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "market_ticks",
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("instrument", sa.String(128), nullable=False),
        sa.Column("asset_class", sa.String(32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("price", sa.Numeric(24, 8), nullable=False),
        sa.Column("bid", sa.Numeric(24, 8), nullable=True),
        sa.Column("ask", sa.Numeric(24, 8), nullable=True),
        sa.Column("open", sa.Numeric(24, 8), nullable=True),
        sa.Column("high", sa.Numeric(24, 8), nullable=True),
        sa.Column("low", sa.Numeric(24, 8), nullable=True),
        sa.Column("close", sa.Numeric(24, 8), nullable=True),
        sa.Column("volume", sa.Numeric(30, 8), nullable=True),
        sa.Column("value", sa.Numeric(30, 8), nullable=True),
        sa.Column("currency", sa.String(12), nullable=False, server_default="IRR"),
        sa.Column("decision_basis", sa.String(16), nullable=False, server_default="dual"),
        sa.Column("quality_flag", sa.String(16), nullable=False, server_default="clean"),
        sa.Column("quality_reasons", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("raw_object_key", sa.Text(), nullable=True),
        sa.Column("raw_sha256", sa.String(64), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("source", "instrument", "observed_at"),
    )
    op.create_index("ix_market_ticks_instrument_time", "market_ticks", ["instrument", "observed_at"])
    op.create_index("ix_market_ticks_quality_time", "market_ticks", ["quality_flag", "observed_at"])
    op.execute(
        "SELECT create_hypertable('market_ticks', 'observed_at', "
        "chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE)"
    )

    op.create_table(
        "market_data_quality_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("instrument", sa.String(128), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(128), nullable=False),
        sa.Column("details", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_quality_events_source_time", "market_data_quality_events", ["source", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_quality_events_source_time", table_name="market_data_quality_events")
    op.drop_table("market_data_quality_events")
    op.drop_index("ix_market_ticks_quality_time", table_name="market_ticks")
    op.drop_index("ix_market_ticks_instrument_time", table_name="market_ticks")
    op.drop_table("market_ticks")
    op.drop_table("market_data_sources")
