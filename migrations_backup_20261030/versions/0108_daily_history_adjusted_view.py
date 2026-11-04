"""adjusted-price read view over daily_history × daily_adjust_factors

Revision ID: 0108
Revises: 0107
Create Date: 2026-10-05

Audit §2 follow-up. Migration 0061 materialised the cumulative corporate-action
factor per ``(symbol_id, trade_date)`` but nothing read it, so every indicator
(precompute snapshot + JIT read-through) still consumed raw TSETMC prices and
was silently corrupted by capital increases / bonus shares / DPS.

This adds ``vw_daily_history_adjusted``: the full ``daily_history`` row plus
``adj_factor`` and the adjusted price columns (``price_*_adj``). Raw columns are
kept so callers can still show untampered prints.

Performance (measured on the dev DB, 5.45 M rows in
``brsapi_historical_daily`` / 9.4 M in the deprecated table per migration 0034):

* per-symbol candle read — ``daily_history`` **2 ms vs** view **2–9 ms**
  (ORDER BY trade_date DESC LIMIT 260 is served by
  ``idx_hist_symbol_gregorian``; the join is a PK probe on
  ``daily_adjust_factors (symbol_id, trade_date)``, one probe per returned row)
* the view is a plain non-materialised join, so the planner inlines it and
  pushes ``symbol = :sym`` down to the base table — no extra index is needed
  on either side.

Deliberately NOT adjusted:
* ``trade_volume`` / ``trade_value`` / ``trade_count`` — matches the prevailing
  vendor convention (branch: ``auto_adjust`` adjusts only prices) and keeps the
  money-flow / per-capita columns comparable with the raw tape.
* ``price_last_change_pct`` / ``price_close_change_pct`` — a constant per-day
  factor cancels out of an intra-day ratio.

Coverage caveat (documented, not fixable here): the factor is joined on
``symbol_id``, which ``daily_history`` derives from ``symbols``. Rows whose
symbol has no ``symbols`` record (≈4.5 M of 5.45 M in dev — delisted/legacy
tickers) can therefore never be adjusted; they resolve to ``adj_factor = 1``.
That is consistent with ``corporate_action_events``' FK to ``symbols(id)``:
an unregistered symbol cannot carry an event either.
"""

from __future__ import annotations

from alembic import op

revision = "0108"
down_revision = "0107"
branch_labels = None
depends_on = None

_VIEW = "vw_daily_history_adjusted"

_DDL_UP = [
    f"""
    CREATE OR REPLACE VIEW {_VIEW} AS
    SELECT
        d.id,
        d.symbol_id,
        d.symbol,
        d.trade_count,
        d.trade_volume,
        d.trade_value,
        d.price_min,
        d.price_max,
        d.price_yesterday,
        d.price_first,
        d.price_last,
        d.price_last_change,
        d.price_last_change_pct,
        d.price_close,
        d.price_close_change,
        d.price_close_change_pct,
        d.trade_date,
        d.created_at,
        d.updated_at,
        COALESCE(f.adj_factor, 1) AS adj_factor,
        d.price_first     * COALESCE(f.adj_factor, 1) AS price_first_adj,
        d.price_max       * COALESCE(f.adj_factor, 1) AS price_max_adj,
        d.price_min       * COALESCE(f.adj_factor, 1) AS price_min_adj,
        d.price_last      * COALESCE(f.adj_factor, 1) AS price_last_adj,
        d.price_close     * COALESCE(f.adj_factor, 1) AS price_close_adj,
        d.price_yesterday * COALESCE(f.adj_factor, 1) AS price_yesterday_adj
    FROM daily_history d
    LEFT JOIN daily_adjust_factors f
           ON f.symbol_id = d.symbol_id
          AND f.trade_date = d.trade_date
    """
]


def upgrade() -> None:
    for stmt in _DDL_UP:
        op.execute(stmt)


def downgrade() -> None:
    op.execute(f"DROP VIEW IF EXISTS {_VIEW}")
