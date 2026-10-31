"""
Deprecate legacy tables & create views onto brsapi_* tables
------------------------------------------------------------

Migrates 5 legacy tables that have been superseded by brsapi_* equivalents:

+--------------------------+--------------------------+--------+--------+
| Old table                | New table                | Old r. | New r. |
+==========================+==========================+========+========+
| daily_history            | brsapi_historical_daily  |  89 K  | 9.4 M  |
| symbol_snapshots         | brsapi_symbol_snapshots  |   0    | 1.1 M  |
| intraday_trades          | brsapi_intraday_trades   | 9.1 M  | 1.6 M  |
| candlesticks             | brsapi_candlesticks      |   0    | 791 K  |
| codal_announcements      | brsapi_codal_announcements|   0   |  5 K   |
+--------------------------+--------------------------+--------+--------+

Important
---------
* The old ``intraday_trades`` table is NOT empty — it has **9.1 M rows**
  (the new table only has 1.6 M).  The view uses ``UNION ALL`` so no data
  is lost.  Once the brsapi_* backfill catches up, the UNION can be
  removed and the old table dropped.

* ``symbol_id`` (FK → ``symbols.id``) does not exist in the new tables.
  Views that need it use a LEFT JOIN with the ``symbols`` table via the
  ``symbol`` text column.

* ``trade_date`` is mapped from ``gregorian_date`` (the dual-date trigger
  column derived from ``created_at`` — this is the **fetch date**, not the
  actual trade date).  For true trade dates, run ``scripts/backfill_dates.py``
  first, which creates ``trade_date_utc``; then update the view to use it.

Run order
---------
  1. ``python scripts/backfill_dates.py``    (adds TIMESTAMPTZ columns)
  2. ``alembic upgrade head``                (rename + create views)

Revision ID:     0034_deprecate_old_tables_create_views
Revises:         0033_add_shareholder_id
Create Date:     2026-08-10
"""

from __future__ import annotations

from alembic import op

revision = "0034_deprecate_old_tables_create_views"
down_revision = "0033_add_shareholder_id"
branch_labels = None
depends_on = None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _rename_table(old: str, new: str) -> None:
    op.rename_table(old, new)


def _drop_view(name: str) -> None:
    op.execute(f'DROP VIEW IF EXISTS "{name}" CASCADE')


def _create_or_replace_view(name: str, select_sql: str) -> None:
    op.execute(f'CREATE OR REPLACE VIEW "{name}" AS {select_sql}')


# ── Upgrade ──────────────────────────────────────────────────────────────────

def upgrade() -> None:
    # ── 1. daily_history → daily_history_deprecated ─────────────────────
    _rename_table("daily_history", "daily_history_deprecated")
    _create_or_replace_view("daily_history", """
        SELECT
            h.id                           AS id,
            s.id                           AS symbol_id,
            h.symbol                       AS symbol,
            h.trade_count                  AS trade_count,
            h.trade_volume                 AS trade_volume,
            h.trade_value                  AS trade_value,
            h.price_min                    AS price_min,
            h.price_max                   AS price_max,
            h.price_yesterday              AS price_yesterday,
            h.price_first                  AS price_first,
            h.price_last                   AS price_last,
            h.price_last_change            AS price_last_change,
            h.price_last_change_pct        AS price_last_change_pct,
            h.price_close                  AS price_close,
            h.price_close_change           AS price_close_change,
            h.price_close_change_pct       AS price_close_change_pct,
            h.gregorian_date               AS trade_date,
            h.created_at                   AS created_at,
            h.updated_at                   AS updated_at
        FROM brsapi_historical_daily h
        LEFT JOIN symbols s ON s.symbol = h.symbol
    """)

    # ── 2. symbol_snapshots → symbol_snapshots_deprecated ───────────────
    _rename_table("symbol_snapshots", "symbol_snapshots_deprecated")
    _create_or_replace_view("symbol_snapshots", """
        SELECT
            s.id                           AS id,
            sym.id                         AS symbol_id,
            s.symbol                       AS symbol,
            s.time                         AS time,
            s.price_last                   AS price_last,
            s.price_close                  AS price_close,
            s.price_first                  AS price_first,
            s.price_yesterday              AS price_yesterday,
            s.price_close_change           AS price_close_change,
            s.price_close_change_pct       AS price_close_change_pct,
            s.price_min                    AS price_min,
            s.price_max                   AS price_max,
            s.trade_count                  AS trade_count,
            s.trade_volume                 AS trade_volume,
            s.trade_value                  AS trade_value,
            s.ins_id                       AS ins_id,
            s.gregorian_date               AS gregorian_date,
            s.shamsi_date                  AS shamsi_date
        FROM brsapi_symbol_snapshots s
        LEFT JOIN symbols sym ON sym.symbol = s.symbol
    """)

    # ── 3. intraday_trades → intraday_trades_deprecated ─────────────────
    # WARNING: old table has 9.1 M rows vs new table 1.6 M.
    # UNION ALL preserves all data until the backfill catches up.
    # NOTE: the legacy table uses (symbol_id, seq_no, is_canceled) columns,
    # NOT (id, symbol, canceled). The UNION maps the legacy rows onto the
    # new view's column list with explicit casts so both branches line up.
    _rename_table("intraday_trades", "intraday_trades_deprecated")
    _create_or_replace_view("intraday_trades", """
        SELECT
            t.id                           AS id,
            sym.id                         AS symbol_id,
            t.symbol                       AS symbol,
            t.trade_date                   AS trade_date,
            t.time                         AS time,
            t.volume                       AS volume,
            t.price                        AS price,
            t.created_at                   AS created_at,
            t.gregorian_date               AS gregorian_date,
            t.shamsi_date                  AS shamsi_date
        FROM brsapi_intraday_trades t
        LEFT JOIN symbols sym ON sym.symbol = t.symbol
        UNION ALL
        SELECT
            NULL::bigint                             AS id,
            o.symbol_id                              AS symbol_id,
            sym.symbol                               AS symbol,
            o.trade_date::character varying          AS trade_date,
            o.time::character varying                AS time,
            o.volume                                 AS volume,
            o.price::double precision                AS price,
            NULL::timestamp without time zone        AS created_at,
            o.gregorian_date                         AS gregorian_date,
            o.shamsi_date                            AS shamsi_date
        FROM intraday_trades_deprecated o
        LEFT JOIN symbols sym ON sym.id = o.symbol_id
    """)

    # ── 4. candlesticks → candlesticks_deprecated ───────────────────────
    _rename_table("candlesticks", "candlesticks_deprecated")
    _create_or_replace_view("candlesticks", """
        SELECT
            c.id                           AS id,
            sym.id                         AS symbol_id,
            c.symbol                       AS symbol,
            c.candle_type                  AS candle_type,
            c.time                         AS time,
            c.open                         AS open,
            c.high                         AS high,
            c.low                          AS low,
            c.close                        AS close,
            c.volume                       AS volume,
            c.gregorian_date               AS gregorian_date,
            c.shamsi_date                  AS shamsi_date
        FROM brsapi_candlesticks c
        LEFT JOIN symbols sym ON sym.symbol = c.symbol
    """)

    # ── 5. codal_announcements → codal_announcements_deprecated ─────────
    _rename_table("codal_announcements", "codal_announcements_deprecated")
    _create_or_replace_view("codal_announcements", """
        SELECT
            ca.id                          AS id,
            ca.symbol                      AS symbol,
            ca.title                       AS title,
            ca.code                        AS code,
            ca.date_title                  AS date_title,
            ca.date_send                   AS date_send,
            ca.date_publish                AS date_publish,
            ca.link                        AS link,
            ca.link_pdf                    AS link_pdf,
            ca.link_excel                  AS link_excel,
            ca.created_at                  AS created_at,
            ca.gregorian_date              AS gregorian_date,
            ca.shamsi_date                 AS shamsi_date
        FROM brsapi_codal_announcements ca
        LEFT JOIN symbols sym ON sym.symbol = ca.symbol
    """)


# ── Downgrade ────────────────────────────────────────────────────────────────

def downgrade() -> None:
    """Drop views and restore original table names."""
    # Drop views first (order doesn't matter for DROP VIEW)
    for view in ("daily_history", "symbol_snapshots", "intraday_trades",
                 "candlesticks", "codal_announcements"):
        _drop_view(view)

    # Restore original table names
    _rename_table("daily_history_deprecated", "daily_history")
    _rename_table("symbol_snapshots_deprecated", "symbol_snapshots")
    _rename_table("intraday_trades_deprecated", "intraday_trades")
    _rename_table("candlesticks_deprecated", "candlesticks")
    _rename_table("codal_announcements_deprecated", "codal_announcements")
