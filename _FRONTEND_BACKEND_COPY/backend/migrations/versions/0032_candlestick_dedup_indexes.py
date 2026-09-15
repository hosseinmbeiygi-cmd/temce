"""Candlestick dedup + dual-date backfill for ``brsapi_candlesticks``.

The candlestick sync used to leave ``candle_type`` NULL (so the data was
invisible to ``get_candlesticks``) and the table had no unique index (so
repeated syncs appended duplicate bars). This migration:

- ensures ``gregorian_date`` / ``shamsi_date`` exist (0025 added them to every
  table, kept here idempotently for fresh chains)
- registers the table in ``dual_date_columns`` (source = ``date``) and ensures
  the ``trg_dual_dates`` trigger exists so future inserts auto-fill the columns
- backfills the dual-date columns from the Jalali ``date`` column
- removes unreadable legacy rows (NULL ``candle_type``) and dedupes by
  ``(symbol, date, time, candle_type)`` keeping the newest ``id``
- creates a UNIQUE index so the generic ``ON CONFLICT DO NOTHING`` bulk insert
  becomes idempotent, plus a ``(symbol, gregorian_date, candle_type)`` index
  for chronologically-ordered reads

Revision ID: 0032_candlestick_dedup_indexes
Revises: 0031_add_avg_50d_volume
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0032_candlestick_dedup_indexes"
down_revision = "0031_add_avg_50d_volume"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1) Dual-date columns (idempotent — 0025 already added them everywhere)
    conn.execute(text("ALTER TABLE brsapi_candlesticks ADD COLUMN IF NOT EXISTS gregorian_date date"))
    conn.execute(text("ALTER TABLE brsapi_candlesticks ADD COLUMN IF NOT EXISTS shamsi_date varchar(10)"))

    # 2) Register the source column so sync_dual_dates_fn fills the columns.
    #    NOTE: migration 0025 auto-picked ``created_at`` for this table (its
    #    priority list found no populated date column) — the real source is the
    #    API's Jalali ``date`` column, so overwrite it.
    conn.execute(
        text(
            "INSERT INTO dual_date_columns (table_name, source_column) "
            "VALUES ('brsapi_candlesticks', 'date') "
            "ON CONFLICT (table_name) DO UPDATE SET source_column = EXCLUDED.source_column"
        )
    )
    # 3) Ensure the BEFORE INSERT/UPDATE trigger exists (0025 creates it for
    #    every sourced table, but keep this idempotent for fresh chains).
    conn.execute(
        text(
            "DO $$ BEGIN "
            "  IF NOT EXISTS (SELECT 1 FROM pg_trigger "
            "                 WHERE tgname = 'trg_dual_dates' "
            "                   AND tgrelid = 'brsapi_candlesticks'::regclass) THEN "
            "    CREATE TRIGGER trg_dual_dates BEFORE INSERT OR UPDATE "
            "      ON brsapi_candlesticks FOR EACH ROW "
            "      EXECUTE FUNCTION sync_dual_dates_fn(); "
            "  END IF; "
            "END $$;"
        )
    )

    # 4) Drop unreadable legacy rows (NULL candle_type was produced by the old
    #    buggy sync and can never be selected by get_candlesticks) and dedupe
    #    by (symbol, date, time, candle_type), keeping the newest id.
    conn.execute(text("DELETE FROM brsapi_candlesticks WHERE candle_type IS NULL OR date IS NULL OR date = ''"))
    conn.execute(
        text(
            "DELETE FROM brsapi_candlesticks a USING brsapi_candlesticks b "
            "WHERE a.id < b.id "
            "  AND a.symbol = b.symbol AND a.date = b.date "
            "  AND COALESCE(a.time, '') = COALESCE(b.time, '') "
            "  AND COALESCE(a.candle_type, '') = COALESCE(b.candle_type, '')"
        )
    )

    # 5) Backfill dual dates from the raw Jalali date column (unconditional —
    #    any pre-existing values were derived from ``created_at`` and are wrong).
    conn.execute(
        text(
            "UPDATE brsapi_candlesticks SET "
            "  gregorian_date = any_to_miladi(date), "
            "  shamsi_date = miladi_to_shamsi(any_to_miladi(date)) "
            "WHERE date IS NOT NULL AND date <> ''"
        )
    )

    # 6) Unique index → ON CONFLICT DO NOTHING becomes idempotent
    conn.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_candle_symbol_date_time_type "
            "ON brsapi_candlesticks (symbol, date, time, candle_type)"
        )
    )
    # 7) Chronological-read index
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_candle_symbol_gregorian "
            "ON brsapi_candlesticks (symbol, gregorian_date, candle_type)"
        )
    )

    print("  OK Migration 0032 complete: candlestick dedup + dual-date backfill")


def downgrade() -> None:
    op.drop_index("idx_candle_symbol_gregorian", table_name="brsapi_candlesticks")
    op.drop_index("uq_candle_symbol_date_time_type", table_name="brsapi_candlesticks")
    conn = op.get_bind()
    conn.execute(
        text(
            "DO $$ BEGIN "
            "  IF EXISTS (SELECT 1 FROM pg_trigger "
            "             WHERE tgname = 'trg_dual_dates' "
            "               AND tgrelid = 'brsapi_candlesticks'::regclass) THEN "
            "    DROP TRIGGER trg_dual_dates ON brsapi_candlesticks; "
            "  END IF; "
            "END $$;"
        )
    )
    print("  OK Downgrade 0032 complete")
