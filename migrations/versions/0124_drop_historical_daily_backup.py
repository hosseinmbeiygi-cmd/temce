"""0124 - Drop brsapi_historical_daily_backup table.

The backup table was created as a one-time safety net before a schema change
and was never truncated or removed.  At ~0.98 GiB it wastes storage and
confuses freshness monitoring.  F9: drop it.
"""

from __future__ import annotations

from alembic import op

revision = "0124"
down_revision = "0123_ingestion_core_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS brsapi_historical_daily_backup")


def downgrade() -> None:
    # The backup cannot be restored automatically; re-create it manually if
    # needed: CREATE TABLE brsapi_historical_daily_backup AS
    #          SELECT * FROM brsapi_historical_daily;
    pass
