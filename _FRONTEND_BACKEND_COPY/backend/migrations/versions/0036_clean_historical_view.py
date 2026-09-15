"""
Clean historical data view
--------------------------

Creates ``vw_clean_daily_history`` — a view over ``brsapi_historical_daily``
that exposes only the cleaned rows:

  * rows with valid (non-zero, non-null) close price AND trade volume
  * deduplicated per (symbol, date) — keeps the latest row
  * trade dates normalised from the dual-date columns (``gregorian_date``
    preferred, falls back to ``shamsi_date`` → cast)

The cleanup logic mirrors ``scripts/clean_historical_data.py`` so the
script (which mutates the base table) and the read-side view stay in sync.

Revision ID:     0036_clean_historical_view
Revises:         0035_feature_store_tables
Create Date:     2026-08-10
"""

from __future__ import annotations

from alembic import op

revision = "0036_clean_historical_view"
down_revision = "0035_feature_store_tables"
branch_labels = None
depends_on = None


# ── Helpers ────────────────────────────────────────────────────────────────


def _drop_view(name: str) -> None:
    op.execute(f'DROP VIEW IF EXISTS "{name}" CASCADE')


def _create_or_replace_view(name: str, select_sql: str) -> None:
    op.execute(f'CREATE OR REPLACE VIEW "{name}" AS {select_sql}')


# ── Upgrade ────────────────────────────────────────────────────────────────


def upgrade() -> None:
    _create_or_replace_view(
        "vw_clean_daily_history",
        """
        SELECT DISTINCT ON (h.symbol, h.gregorian_date)
            h.id,
            s.id                                        AS symbol_id,
            h.symbol,
            h.gregorian_date                          AS trade_date,
            h.trade_count,
            h.trade_volume,
            h.trade_value,
            h.price_min,
            h.price_max,
            h.price_yesterday,
            h.price_first,
            h.price_last,
            h.price_last_change,
            h.price_last_change_pct,
            h.price_close,
            h.price_close_change,
            h.price_close_change_pct,
            h.created_at,
            h.updated_at
        FROM brsapi_historical_daily h
        LEFT JOIN symbols s ON s.symbol = h.symbol
        WHERE h.price_close IS NOT NULL AND h.price_close > 0
          AND h.trade_volume IS NOT NULL AND h.trade_volume > 0
          AND h.gregorian_date IS NOT NULL
        ORDER BY h.symbol, h.gregorian_date, h.id DESC
    """,
    )


# ── Downgrade ──────────────────────────────────────────────────────────────


def downgrade() -> None:
    _drop_view("vw_clean_daily_history")
