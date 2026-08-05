"""Add dual (Gregorian + Shamsi) date columns to every public table.

Schema-only migration:
  - installs the Jalali conversion functions + ``dual_date_columns`` meta
    table + the generic ``sync_dual_dates_fn`` trigger function
  - adds ``gregorian_date date`` / ``shamsi_date varchar(10)`` to every table
  - auto-picks a primary date source column per table (``dual_date_columns``)
  - creates a BEFORE INSERT/UPDATE trigger so both columns stay in sync

Data backfill is intentionally NOT done here (it would lock huge tables for a
long time). Run ``scripts/backfill_dual_dates.py`` afterwards — it backfills
all tables with the same conversions using ``jdatetime`` and commits per
table. The conversion core lives in ``scripts/install_dual_dates.py``.

Revision ID: 0025_add_dual_date_columns
Revises: 0024_add_user_telegram_chat_id
"""
from __future__ import annotations

import sys
from pathlib import Path

from alembic import op
from sqlalchemy import text

# env.py only adds the project root to sys.path when running ``upgrade``;
# commands like ``alembic heads``/``history`` import migration modules without
# it, so make sure the ``scripts`` package resolves in every alembic command.
_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# The conversion SQL lives in scripts/install_dual_dates.py (single source of
# truth, also used by scripts/backfill_dual_dates.py). Migrations are normally
# frozen snapshots; this deliberate shared import keeps the 10 conversion
# functions in one place — do not change that module after this migration ships.
from scripts.install_dual_dates import FUNCS  # noqa: E402

revision = "0025_add_dual_date_columns"
down_revision = "0024_add_user_telegram_chat_id"
branch_labels = None
depends_on = None

# Preferred source columns, in order. Columns are only considered when they
# hold date-ish data; pure time columns are skipped.
_PRIORITY = [
    "trade_date",
    "date_publish",
    "publish_date",
    "date_published",
    "snapshot_date",
    "date_price_settlement",
    "date_trade",
    "date_delivery",
    "date_end",
    "start_date",
    "end_date",
    "last_trade_date",
    "report_date",
    "financial_date",
    "pub_date",
    "fetched_at",
    "created_at",
    "updated_at",
    "date",
]

_TIME_TYPES = {"time without time zone", "time with time zone"}


def _tables(conn) -> list[str]:
    rows = conn.execute(
        text(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname = 'public' AND tablename NOT LIKE 'alembic_%' "
            "ORDER BY tablename"
        )
    ).fetchall()
    return [r[0] for r in rows]


def _columns(conn, table: str) -> dict[str, str]:
    """Return {column_name: data_type} for a table."""
    rows = conn.execute(
        text(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :t ORDER BY ordinal_position"
        ),
        {"t": table},
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def _has_data(conn, table: str, col: str) -> bool:
    row = conn.execute(
        text(f'SELECT 1 FROM "{table}" WHERE "{col}" IS NOT NULL LIMIT 1')
    ).first()
    return row is not None


def _pick_source(conn, table: str, cols: dict[str, str]) -> str | None:
    """Pick the primary date source column for a table (or None)."""
    names = {c for c in cols if c not in ("gregorian_date", "shamsi_date")}
    usable = [c for c in names if cols.get(c) not in _TIME_TYPES]

    # 1) priority list, with data present
    for name in _PRIORITY:
        if name in usable and _has_data(conn, table, name):
            return name
    # 2) priority list, regardless of data (future inserts still get dates)
    for name in _PRIORITY:
        if name in usable:
            return name
    # 3) any *_date / date column with data
    for name in sorted(usable):
        if (name == "date" or name.endswith("_date")) and _has_data(conn, table, name):
            return name
    # 4) any *_date / date column, regardless of data
    for name in sorted(usable):
        if name == "date" or name.endswith("_date"):
            return name
    return None


def upgrade() -> None:
    conn = op.get_bind()

    # 1) conversion functions + meta table + trigger function
    for stmt in FUNCS:
        conn.execute(text(stmt))
    # fresh meta table (the previous run may have left test rows behind)
    conn.execute(text("DELETE FROM dual_date_columns"))

    # 2) add dual date columns to every public table
    tables = _tables(conn)
    for t in tables:
        conn.execute(text(f'ALTER TABLE "{t}" ADD COLUMN IF NOT EXISTS gregorian_date date'))
        conn.execute(text(f'ALTER TABLE "{t}" ADD COLUMN IF NOT EXISTS shamsi_date varchar(10)'))

    # 3) source selection + triggers
    n_sourced = 0
    for t in tables:
        cols = _columns(conn, t)
        src = _pick_source(conn, t, cols)
        if src is None:
            continue
        conn.execute(
            text("INSERT INTO dual_date_columns (table_name, source_column) VALUES (:t, :s)"),
            {"t": t, "s": src},
        )
        conn.execute(
            text(f'CREATE TRIGGER trg_dual_dates BEFORE INSERT OR UPDATE ON "{t}" '
                 f'FOR EACH ROW EXECUTE FUNCTION sync_dual_dates_fn()')
        )
        n_sourced += 1

    print(
        f"dual-date schema ready on {len(tables)} tables; source+trigger on {n_sourced}. "
        f"Backfill data with: python scripts/backfill_dual_dates.py"
    )


def downgrade() -> None:
    conn = op.get_bind()
    for t in _tables(conn):
        conn.execute(text(f'DROP TRIGGER IF EXISTS trg_dual_dates ON "{t}"'))
        conn.execute(text(f'ALTER TABLE "{t}" DROP COLUMN IF EXISTS shamsi_date'))
        conn.execute(text(f'ALTER TABLE "{t}" DROP COLUMN IF EXISTS gregorian_date'))
    conn.execute(text("DELETE FROM dual_date_columns"))
