from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ml_models",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("task", sa.String(50), nullable=True, server_default="classification"),
        sa.Column("framework", sa.String(50), nullable=True, server_default="sklearn"),
        sa.Column("latest_version", sa.String(20), nullable=True, server_default="1.0.0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "ml_model_versions",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("model_id", sa.String(50), sa.ForeignKey("ml_models.id"), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("stage", sa.String(20), nullable=True, server_default="development"),
        sa.Column("metrics", sa.Text(), nullable=True),
        sa.Column("parameters", sa.Text(), nullable=True),
        sa.Column("artifact_path", sa.Text(), nullable=True),
        sa.Column("dataset_snapshot", sa.String(100), nullable=True),
        sa.Column("training_run_id", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.create_table(
        "ml_training_runs",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("experiment_name", sa.String(200), nullable=True),
        sa.Column("run_name", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=True, server_default="pending"),
        sa.Column("model_type", sa.String(50), nullable=True),
        sa.Column("config", sa.Text(), nullable=True),
        sa.Column("metrics", sa.Text(), nullable=True),
        sa.Column("best_params", sa.Text(), nullable=True),
        sa.Column("progress_pct", sa.Float(), nullable=True, server_default="0"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("ml_training_runs")
    op.drop_table("ml_model_versions")
    op.drop_table("ml_models")
