"""Create signal_accuracy table for feedback loop outcome tracking.

The QuantSignalOrchestrator's feedback loop depends on this table:
  - _persist_pending_signals() → INSERTs signals with NULL outcome_set_at
  - _evaluate_past_signals() → UPDATEs outcomes after prediction period
  - SignalAccuracyTracker → queries accuracy by market/source/symbol
  - AutoRetrainPipeline → checks accuracy to decide whether to retrain

Revision ID: 0007
Revises: 0006_add_missing_updated_at
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006_add_missing_updated_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if table already exists (e.g., created by ORM auto-create in dev)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    table_exists = "signal_accuracy" in inspector.get_table_names()

    if not table_exists:
        op.create_table(
            "signal_accuracy",
            # Primary key
            sa.Column("id", sa.String(50), primary_key=True),
            # Signal identity
            sa.Column("signal_id", sa.String(50), nullable=True),
            sa.Column("symbol", sa.String(50), nullable=False),
            sa.Column("market", sa.String(30), nullable=False),
            sa.Column("source", sa.String(100), nullable=False, server_default="rule_based"),
            sa.Column("direction", sa.String(10), nullable=False, server_default="hold"),
            sa.Column("timeframe", sa.String(10), nullable=False, server_default="daily"),
            # Outcome fields — set after prediction period ends
            sa.Column("actual_return_pct", sa.Float(), nullable=True),
            sa.Column("direction_correct", sa.Boolean(), nullable=True),
            sa.Column("max_profit_pct", sa.Float(), nullable=True),
            sa.Column("max_loss_pct", sa.Float(), nullable=True),
            sa.Column("hit_target1", sa.Boolean(), nullable=True, server_default=sa.text("false")),
            sa.Column("hit_target2", sa.Boolean(), nullable=True, server_default=sa.text("false")),
            sa.Column("stopped_out", sa.Boolean(), nullable=True, server_default=sa.text("false")),
            # Price metadata
            sa.Column("entry_price", sa.Float(), nullable=True),
            sa.Column("exit_price", sa.Float(), nullable=True),
            sa.Column("signal_price", sa.Float(), nullable=True),
            sa.Column("signal_strength", sa.Float(), nullable=True),
            sa.Column("signal_confidence", sa.Float(), nullable=True),
            # Model scores
            sa.Column("ml_score", sa.Float(), nullable=True),
            sa.Column("rule_score", sa.Float(), nullable=True),
            # Timestamps (from TimestampMixin)
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("generated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.Column("outcome_set_at", sa.DateTime(), nullable=True),
            # Extra
            sa.Column("notes", sa.Text(), nullable=True),
        )

    # ── Indexes for query patterns (always create — IF NOT EXISTS safe) ──

    # Lookup by signal_id (used by SignalAccuracyTracker.record_outcome)
    op.create_index("ix_signal_accuracy_signal_id", "signal_accuracy", ["signal_id"])

    # Lookup by symbol (used by get_accuracy_by_symbol)
    op.create_index("ix_signal_accuracy_symbol", "signal_accuracy", ["symbol"])

    # Lookup by market (used by get_accuracy_by_market)
    op.create_index("ix_signal_accuracy_market", "signal_accuracy", ["market"])

    # Lookup by source
    op.create_index("ix_signal_accuracy_source", "signal_accuracy", ["source"])

    # Lookup by direction_correct (used in accuracy aggregation queries)
    op.create_index("ix_signal_accuracy_direction_correct", "signal_accuracy", ["direction_correct"])

    # ── Composite indexes for common queries ──

    # Get accuracy by market + source within a date range
    # Used by: get_accuracy_by_market() — WHERE market=? AND outcome_set_at >= ?
    op.execute(
        sa.text("""
        CREATE INDEX IF NOT EXISTS ix_signal_accuracy_market_outcome
        ON signal_accuracy (market, source, outcome_set_at DESC);
    """)
    )

    # Get accuracy by symbol within a date range
    # Used by: get_accuracy_by_symbol() — WHERE symbol=? AND outcome_set_at >= ?
    op.execute(
        sa.text("""
        CREATE INDEX IF NOT EXISTS ix_signal_accuracy_symbol_outcome
        ON signal_accuracy (symbol, outcome_set_at DESC);
    """)
    )

    # Find pending signals for evaluation (orchestrator feedback loop)
    # Used by: _evaluate_past_signals() — WHERE outcome_set_at IS NULL AND generated_at BETWEEN ?
    op.execute(
        sa.text("""
        CREATE INDEX IF NOT EXISTS ix_signal_accuracy_pending_eval
        ON signal_accuracy (generated_at)
        WHERE outcome_set_at IS NULL;
    """)
    )


def downgrade() -> None:
    op.drop_table("signal_accuracy")
