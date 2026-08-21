"""0040 – Unique constraints for upsert safety + missing indexes.

Revision ID: 0040
Revises: 0039
Create Date: 2026-08-21
"""
import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039_brsapi_daily_usage"
branch_labels = None
depends_on = None


def _safe_create_unique(conn, table: str, columns: list[str], name: str) -> None:
    """Create a unique index only if it doesn't already exist."""
    row = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE tablename = :t AND indexname = :n"
        ),
        {"t": table, "n": name},
    ).fetchone()
    if row is None:
        cols = ", ".join(columns)
        conn.execute(sa.text(f'CREATE UNIQUE INDEX {name} ON {table} ({cols})'))
        print(f"  + unique index {name} on {table}({cols})")
    else:
        print(f"  = unique index {name} already exists")


def _safe_drop_index(conn, name: str) -> None:
    row = conn.execute(
        sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :n"), {"n": name}
    ).fetchone()
    if row is not None:
        conn.execute(sa.text(f"DROP INDEX {name}"))
        print(f"  - dropped index {name}")


def _safe_dedup_and_create_unique(conn, table: str, columns: list[str], name: str) -> None:
    """Deduplicate then create unique index.  Skips if table is empty or
    already has the index.  Only handles tables with <500K duplicates
    to avoid long-running locks.
    """
    row = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE tablename = :t AND indexname = :n"
        ),
        {"t": table, "n": name},
    ).fetchone()
    if row is not None:
        print(f"  = unique index {name} already exists")
        return

    # Count duplicates
    col_expr = " || '|-' || ".join(
        f"COALESCE({c}::text,'')" for c in columns
    )
    dup_sql = (
        "SELECT COUNT(*) FROM ("
        f" SELECT {col_expr} AS key, COUNT(*) AS cnt"
        f" FROM {table}"
        f" GROUP BY {col_expr} HAVING COUNT(*) > 1"
        ") sub"
    )
    dup_count = conn.execute(sa.text(dup_sql)).scalar() or 0
    if dup_count > 500_000:
        print(
            f"  ! skipping {name}: {dup_count}"
            " duplicate groups (too many to dedup)"
        )
        return

    if dup_count > 0:
        print(f"  ~ deduping {table}: {dup_count} duplicate groups...")
        part_cols = ", ".join(columns)
        dedup_sql = (
            "DELETE FROM {} WHERE ctid NOT IN ("
            "SELECT ctid FROM ("
            "SELECT ctid, ROW_NUMBER() OVER ("
            f"PARTITION BY {part_cols} ORDER BY ctid"
            ") AS rn FROM {}"
            ") t WHERE rn > 1"
            ")"
        ).format(table, table)
        conn.execute(sa.text(dedup_sql))
        print("    dedup done")

    cols = ", ".join(columns)
    create_sql = f"CREATE UNIQUE INDEX {name} ON {table} ({cols})"
    conn.execute(sa.text(create_sql))
    print(f"  + unique index {name} on {table}({cols})")


def upgrade() -> None:
    conn = op.get_bind()

    # ── P0: Unique constraints for upsert safety ──────────────────────
    print("Adding unique constraints for safe ON CONFLICT upserts...")

    # Skip brsapi_historical_daily — massive 12M+ row table with 500K+ dup
    # groups; sync already uses ON CONFLICT (symbol, date) DO UPDATE safely.
    # Deferred to a separate batch job.
    print("  ! brsapi_historical_daily: deferred (12M rows, needs batch dedup)")
    # Skip brsapi_intraday_trades — 1.28M duplicate rows; deferred.
    print("  ! brsapi_intraday_trades: deferred (1.28M dups)")
    # Skip codal_reports — 226K rows with NULL isin; deferred.
    print("  ! codal_reports: deferred (226K dups)")

    _safe_create_unique(
        conn, "news_articles",
        ["url"], "uq_news_articles_url",
    )


    # ── P2: Missing indexes for tables > 100K rows ────────────────────
    print("Adding missing indexes...")

    for table, cols, idx_name in [
        ("commodity_certificates", ["symbol"], "ix_commodity_certificates_symbol"),
        ("commodity_trades", ["symbol", "trade_date"], "ix_commodity_trades_symbol_date"),
    ]:
        row = conn.execute(
            sa.text(
                "SELECT 1 FROM pg_indexes WHERE tablename = :t AND indexname = :n"
            ),
            {"t": table, "n": idx_name},
        ).fetchone()
        if row is None:
            col_str = ", ".join(cols)
            conn.execute(sa.text(f"CREATE INDEX {idx_name} ON {table} ({col_str})"))
            print(f"  + index {idx_name} on {table}({col_str})")


def downgrade() -> None:
    conn = op.get_bind()

    for idx in [
        "uq_brsapi_historical_daily_symbol_date",
        "uq_news_articles_url",
        "uq_brsapi_intraday_trades_symbol_date_time",
        "uq_codal_reports_isin_report_type",
        "ix_commodity_certificates_symbol",
        "ix_commodity_trades_symbol_date",
    ]:
        _safe_drop_index(conn, idx)
