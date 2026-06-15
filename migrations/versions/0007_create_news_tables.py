from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "news_articles",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("symbols", sa.Text(), nullable=True),
        sa.Column("published_at", sa.String(30), nullable=True),
        sa.Column("sentiment", sa.String(20), nullable=True, server_default="neutral"),
        sa.Column("sentiment_score", sa.Float(), nullable=True, server_default="0"),
        sa.Column("data_source", sa.String(20), nullable=True, server_default="rss"),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.create_index("ix_news_published_at", "news_articles", ["published_at"])
    op.create_index("ix_news_category", "news_articles", ["category"])


def downgrade() -> None:
    op.drop_index("ix_news_category", table_name="news_articles")
    op.drop_index("ix_news_published_at", table_name="news_articles")
    op.drop_table("news_articles")
