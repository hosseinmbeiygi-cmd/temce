"""Convert brsapi_historical_daily & real_legal to partitioned tables

- Changes PK from (id) to (id, date) for partitioning support
- Converts to PARTITION BY RANGE (date) with yearly partitions
- Creates yearly partition for each year from 1380 to 1406
- Migrates existing data and swaps tables

Revision ID: 0027
Revises: 0026
"""

from __future__ import annotations

from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


# ── Yearly partition boundaries (Shamsi years) ──────────────────
# Data spans 1380-01-05 to 1405-04-09. Create partitions for 1380-1406.

YEARLY_PARTITIONS: list[tuple[str, str, str]] = []
for year in range(1380, 1407):
    next_year = year + 1
    YEARLY_PARTITIONS.append((
        f"brsapi_historical_daily_{year}",
        f"{year}-01-01",
        f"{next_year}-01-01",
    ))

YEARLY_PARTITIONS_RL: list[tuple[str, str, str]] = []
for year in range(1387, 1407):
    next_year = year + 1
    YEARLY_PARTITIONS_RL.append((
        f"brsapi_historical_real_legal_{year}",
        f"{year}-01-01",
        f"{next_year}-01-01",
    ))


def _table_exists(table: str) -> bool:
    """Check if a table exists in the database."""
    from sqlalchemy import text
    conn = op.get_bind()
    try:
        result = conn.execute(
            text("SELECT tablename FROM pg_catalog.pg_tables WHERE tablename = :t"),
            {"t": table},
        )
        return result.fetchone() is not None
    except Exception:
        return False


def _column_names(table: str) -> list[str]:
    """Get all column names for a table."""
    from sqlalchemy import text
    conn = op.get_bind()
    try:
        result = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :t AND table_schema = 'public' "
                "ORDER BY ordinal_position"
            ),
            {"t": table},
        )
        return [row[0] for row in result]
    except Exception:
        return []


def upgrade() -> None:
    # ── 1. brsapi_historical_daily ──────────────────────────────
    if not _table_exists("brsapi_historical_daily"):
        print("SKIP: brsapi_historical_daily does not exist")
    elif _table_exists("brsapi_historical_daily_old"):
        print("SKIP: brsapi_historical_daily already migrated (old table exists)")
    else:
        print("Migrating brsapi_historical_daily to partitioned table...")
        cols = _column_names("brsapi_historical_daily")
        col_list = ", ".join(cols)

        # 1a. Create new partitioned table
        op.execute(f"""
            CREATE TABLE brsapi_historical_daily_new (
                LIKE brsapi_historical_daily INCLUDING DEFAULTS INCLUDING IDENTITY
            ) PARTITION BY RANGE (date)
        """)

        # 1b. Drop ALL inherited constraints and indexes from the new table
        # (LIKE INCLUDING ALL copies indexes, but we need composite PK)
        op.execute("ALTER TABLE brsapi_historical_daily_new DROP CONSTRAINT IF EXISTS brsapi_historical_daily_new_pkey")
        op.execute("DROP INDEX IF EXISTS idx_hist_symbol_date")
        op.execute("DROP INDEX IF EXISTS idx_hist_date")
        op.execute("DROP INDEX IF EXISTS idx_hist_symbol")

        # 1c. Add composite PK
        op.execute("ALTER TABLE brsapi_historical_daily_new ADD PRIMARY KEY (id, date)")

        # 1d. Create yearly partitions
        for part_name, start_date, end_date in YEARLY_PARTITIONS:
            op.execute(f"""
                CREATE TABLE IF NOT EXISTS {part_name}
                PARTITION OF brsapi_historical_daily_new
                FOR VALUES FROM ('{start_date}') TO ('{end_date}')
            """)

        # 1e. Copy data
        op.execute(f"""
            INSERT INTO brsapi_historical_daily_new ({col_list})
            SELECT {col_list} FROM brsapi_historical_daily
        """)

        # 1f. Create indexes on the new table
        op.execute("CREATE INDEX idx_hist_symbol_date ON brsapi_historical_daily_new (symbol, date)")
        op.execute("CREATE INDEX idx_hist_date ON brsapi_historical_daily_new (date)")
        op.execute("CREATE INDEX idx_hist_symbol ON brsapi_historical_daily_new (symbol)")
        op.execute("CREATE INDEX idx_hist_ins_id ON brsapi_historical_daily_new (ins_id)")
        op.execute("CREATE INDEX idx_hist_instrument_id ON brsapi_historical_daily_new (instrument_id)")

        # 1g. Swap tables
        op.execute("ALTER TABLE brsapi_historical_daily RENAME TO brsapi_historical_daily_old")
        op.execute("ALTER TABLE brsapi_historical_daily_new RENAME TO brsapi_historical_daily")

        # 1h. Drop old table
        op.execute("DROP TABLE brsapi_historical_daily_old CASCADE")
        print("  Done.")

    # ── 2. brsapi_historical_real_legal ──────────────────────────
    if not _table_exists("brsapi_historical_real_legal"):
        print("SKIP: brsapi_historical_real_legal does not exist")
    elif _table_exists("brsapi_historical_real_legal_old"):
        print("SKIP: brsapi_historical_real_legal already migrated")
    else:
        print("Migrating brsapi_historical_real_legal to partitioned table...")
        cols = _column_names("brsapi_historical_real_legal")
        col_list = ", ".join(cols)

        # 2a. Create new partitioned table
        op.execute(f"""
            CREATE TABLE brsapi_historical_real_legal_new (
                LIKE brsapi_historical_real_legal INCLUDING DEFAULTS INCLUDING IDENTITY
            ) PARTITION BY RANGE (date)
        """)

        # 2b. Drop ALL inherited constraints and indexes
        op.execute("ALTER TABLE brsapi_historical_real_legal_new DROP CONSTRAINT IF EXISTS brsapi_historical_real_legal_new_pkey")
        op.execute("DROP INDEX IF EXISTS idx_rl_symbol_date")
        op.execute("DROP INDEX IF EXISTS idx_rl_date")
        op.execute("DROP INDEX IF EXISTS idx_rl_symbol")

        # 2c. Add composite PK
        op.execute("ALTER TABLE brsapi_historical_real_legal_new ADD PRIMARY KEY (id, date)")

        # 2d. Create yearly partitions
        for part_name, start_date, end_date in YEARLY_PARTITIONS_RL:
            op.execute(f"""
                CREATE TABLE IF NOT EXISTS {part_name}
                PARTITION OF brsapi_historical_real_legal_new
                FOR VALUES FROM ('{start_date}') TO ('{end_date}')
            """)

        # 2e. Copy data
        op.execute(f"""
            INSERT INTO brsapi_historical_real_legal_new ({col_list})
            SELECT {col_list} FROM brsapi_historical_real_legal
        """)

        # 2f. Create indexes
        op.execute("CREATE INDEX idx_rl_symbol_date ON brsapi_historical_real_legal_new (symbol, date)")
        op.execute("CREATE INDEX idx_rl_date ON brsapi_historical_real_legal_new (date)")
        op.execute("CREATE INDEX idx_rl_symbol ON brsapi_historical_real_legal_new (symbol)")
        op.execute("CREATE INDEX idx_rl_ins_id ON brsapi_historical_real_legal_new (ins_id)")
        op.execute("CREATE INDEX idx_rl_instrument_id ON brsapi_historical_real_legal_new (instrument_id)")

        # 2g. Swap tables
        op.execute("ALTER TABLE brsapi_historical_real_legal RENAME TO brsapi_historical_real_legal_old")
        op.execute("ALTER TABLE brsapi_historical_real_legal_new RENAME TO brsapi_historical_real_legal")

        # 2h. Drop old table
        op.execute("DROP TABLE brsapi_historical_real_legal_old CASCADE")
        print("  Done.")


def downgrade() -> None:
    # ── Reverse historical_daily ──────────────────────────────────
    if not _table_exists("brsapi_historical_daily"):
        return
    # Reconstruct the old table by creating a non-partitioned copy
    cols = _column_names("brsapi_historical_daily")
    col_list = ", ".join(cols)

    op.execute(f"""
        CREATE TABLE brsapi_historical_daily_flat (
            LIKE brsapi_historical_daily INCLUDING ALL
        )
    """)
    op.execute("ALTER TABLE brsapi_historical_daily_flat DROP CONSTRAINT IF EXISTS brsapi_historical_daily_flat_pkey")
    op.execute("ALTER TABLE brsapi_historical_daily_flat ADD PRIMARY KEY (id)")

    op.execute(f"""
        INSERT INTO brsapi_historical_daily_flat ({col_list})
        SELECT {col_list} FROM ONLY brsapi_historical_daily
    """)
    # Also get data from partitions
    for part_name, _, _ in YEARLY_PARTITIONS:
        if _table_exists(part_name):
            op.execute(f"""
                INSERT INTO brsapi_historical_daily_flat ({col_list})
                SELECT {col_list} FROM {part_name}
                WHERE NOT EXISTS (
                    SELECT 1 FROM brsapi_historical_daily_flat WHERE brsapi_historical_daily_flat.id = {part_name}.id
                )
            """)

    op.execute("CREATE INDEX idx_hist_symbol_date ON brsapi_historical_daily_flat (symbol, date)")
    op.execute("CREATE INDEX idx_hist_date ON brsapi_historical_daily_flat (date)")
    op.execute("CREATE INDEX idx_hist_symbol ON brsapi_historical_daily_flat (symbol)")

    op.execute("ALTER TABLE brsapi_historical_daily RENAME TO brsapi_historical_daily_partitioned")
    op.execute("ALTER TABLE brsapi_historical_daily_flat RENAME TO brsapi_historical_daily")
    op.execute("DROP TABLE brsapi_historical_daily_partitioned CASCADE")

    # ── Reverse historical_real_legal ──────────────────────────────
    if not _table_exists("brsapi_historical_real_legal"):
        return

    cols = _column_names("brsapi_historical_real_legal")
    col_list = ", ".join(cols)

    op.execute(f"""
        CREATE TABLE brsapi_historical_real_legal_flat (
            LIKE brsapi_historical_real_legal INCLUDING ALL
        )
    """)
    op.execute("ALTER TABLE brsapi_historical_real_legal_flat DROP CONSTRAINT IF EXISTS brsapi_historical_real_legal_flat_pkey")
    op.execute("ALTER TABLE brsapi_historical_real_legal_flat ADD PRIMARY KEY (id)")

    op.execute(f"""
        INSERT INTO brsapi_historical_real_legal_flat ({col_list})
        SELECT {col_list} FROM ONLY brsapi_historical_real_legal
    """)
    for part_name, _, _ in YEARLY_PARTITIONS_RL:
        if _table_exists(part_name):
            op.execute(f"""
                INSERT INTO brsapi_historical_real_legal_flat ({col_list})
                SELECT {col_list} FROM {part_name}
                WHERE NOT EXISTS (
                    SELECT 1 FROM brsapi_historical_real_legal_flat WHERE brsapi_historical_real_legal_flat.id = {part_name}.id
                )
            """)

    op.execute("CREATE INDEX idx_rl_symbol_date ON brsapi_historical_real_legal_flat (symbol, date)")
    op.execute("CREATE INDEX idx_rl_date ON brsapi_historical_real_legal_flat (date)")
    op.execute("CREATE INDEX idx_rl_symbol ON brsapi_historical_real_legal_flat (symbol)")

    op.execute("ALTER TABLE brsapi_historical_real_legal RENAME TO brsapi_historical_real_legal_partitioned")
    op.execute("ALTER TABLE brsapi_historical_real_legal_flat RENAME TO brsapi_historical_real_legal")
    op.execute("DROP TABLE brsapi_historical_real_legal_partitioned CASCADE")
