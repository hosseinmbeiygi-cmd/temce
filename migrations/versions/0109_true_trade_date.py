"""true trade date for the indicator read path — Gregorian + Shamsi

Revision ID: 0109
Revises: 0108
Create Date: 2026-10-06

Why. ``daily_history`` (view, migration 0034) maps ``trade_date`` from
``gregorian_date``, which is the **fetch** date. Measured on the dev DB
(5.45 M rows): only **17 distinct trade dates**, up to 5,902 rows sharing one
``(symbol, trade_date)``. The "daily" series the indicators consumed was
therefore not daily at all — and the cumulative adjustment factor from 0061
was compounded against fetch dates while ``corporate_action_events.ex_date``
is a real Gregorian date.

The true trade date was already in the table: ``date``, a Shamsi
``YYYY-MM-DD`` string (``shamsi_date`` is fetch-related, not the trade date),
and ``(symbol, date)`` is **unique** (valid index
``uq_brsapi_historical_daily_symbol_date``, 0 duplicate groups). All 6,166
distinct values present are legal Jalali dates.

What this migration does:

1. ``jalali_to_gregorian(text) -> date`` — IMMUTABLE STRICT PARALLEL SAFE
   PL/pgSQL port of the FarsiWeb ``jalali.c`` algorithm that the project's
   installed ``jdatetime`` uses (vendored ``jalali_core``), so SQL and Python
   can never disagree. Validated against ``jdatetime`` on **55,152 dates
   (1300…1450) with 0 mismatches**; illegal dates (e.g. Esfand 30 in a
   non-leap year — 33-year cycle) return NULL, exactly where
   ``jdatetime.date()`` raises.
2. ``vw_daily_history_adjusted`` rebuilt on the base table exposing **both
   calendars**: ``trade_date`` (Gregorian DATE, derived on read) and
   ``trade_date_shamsi`` (the raw Jalali string), plus ``trade_time`` and the
   fetch date for traceability. The adjustment factor is now joined on the
   true Gregorian trade date (``daily_adjust_factors.trade_date`` means that
   from here on).

Why the Gregorian date is derived on read instead of stored in a column:
writing it back means rewriting all 5.45 M rows, and this table carries
**12 indexes**, so every rewritten row also inserts 12 index tuples. Measured
on the dev DB: cancelled after 28 minutes (a per-row converter call was even
worse at >10 min). Deriving it costs one function call per *returned* row —
the per-symbol read path touches ≤ a few hundred rows — and it is never stale
for newly ingested trading days, which a materialised 6,166-row date map
would be. If a global Gregorian range scan is ever needed, add a persisted
column (or an expression index on ``jalali_to_gregorian(date)``) in a
maintenance window; the reader API here would not change.

``daily_history`` itself is untouched: its fetch-date semantics are used by
other consumers (screener, features) and changing it in place would be a
breaking change. The indicator path reads this view instead.

Downgrade restores the 0108 view and drops the function. Indicator rows
computed meanwhile carry the true trade date and must be recomputed after a
downgrade (the precompute is idempotent on ``(symbol, trade_date)``).
"""

from __future__ import annotations

from alembic import op

revision = "0109"
down_revision = "0108"
branch_labels = None
depends_on = None

_VIEW = "vw_daily_history_adjusted"

# PL/pgSQL port of jdatetime's jalali_core.JalaliToGregorian (FarsiWeb
# jalali.c, LGPL) — behaviour-identical to the Python reference, including
# returning NULL for illegal dates instead of rolling over into the next
# month.
_FN = r"""
CREATE OR REPLACE FUNCTION jalali_to_gregorian(jalali text)
RETURNS date
LANGUAGE plpgsql
IMMUTABLE STRICT PARALLEL SAFE
AS $fn$
DECLARE
    j_days constant int[] := ARRAY[31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29];
    g_days constant int[] := ARRAY[31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    jy int;
    jm int;
    jd int;
    max_d int;
    g_day_no int;
    gy int;
    leap int;
    i int;
BEGIN
    IF jalali !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN
        RETURN NULL;
    END IF;
    jy := substring(jalali, 1, 4)::int;
    jm := substring(jalali, 6, 2)::int;
    jd := substring(jalali, 9, 2)::int;
    IF jm < 1 OR jm > 12 THEN
        RETURN NULL;
    END IF;
    -- months 1..6 have 31 days; Esfand (12) has 30 only in a leap year of
    -- the 33-year cycle -- same rule jdatetime.date() enforces
    IF jm = 12 THEN
        max_d := 29 + (CASE WHEN (jy % 33) IN (1, 5, 9, 13, 17, 22, 26, 30) THEN 1 ELSE 0 END);
    ELSE
        max_d := j_days[jm];
    END IF;
    IF jd < 1 OR jd > max_d THEN
        RETURN NULL;
    END IF;

    jy := jy - 979;
    g_day_no := 365 * jy + (jy / 33) * 8 + ((jy % 33) + 3) / 4 + jd - 1 + 79;
    FOR i IN 1 .. (jm - 1) LOOP
        g_day_no := g_day_no + j_days[i];
    END LOOP;

    gy := 1600 + 400 * (g_day_no / 146097);
    g_day_no := g_day_no % 146097;

    leap := 1;
    IF g_day_no >= 36525 THEN
        g_day_no := g_day_no - 1;
        gy := gy + 100 * (g_day_no / 36524);
        g_day_no := g_day_no % 36524;
        IF g_day_no >= 365 THEN
            g_day_no := g_day_no + 1;
        ELSE
            leap := 0;
        END IF;
    END IF;

    gy := gy + 4 * (g_day_no / 1461);
    g_day_no := g_day_no % 1461;

    IF g_day_no >= 366 THEN
        leap := 0;
        g_day_no := g_day_no - 1;
        gy := gy + (g_day_no / 365);
        g_day_no := g_day_no % 365;
    END IF;

    i := 0;
    LOOP
        max_d := g_days[i + 1] + (CASE WHEN i = 1 AND leap = 1 THEN 1 ELSE 0 END);
        EXIT WHEN g_day_no < max_d;
        g_day_no := g_day_no - max_d;
        i := i + 1;
    END LOOP;

    RETURN make_date(gy, i + 1, g_day_no + 1);
END;
$fn$;
"""

# Kept for downgrade symmetry (0108 shape, fetch-date + no calendar columns).
_VIEW_0108 = """
CREATE VIEW vw_daily_history_adjusted AS
SELECT
    d.id, d.symbol_id, d.symbol, d.trade_count, d.trade_volume, d.trade_value,
    d.price_min, d.price_max, d.price_yesterday, d.price_first, d.price_last,
    d.price_last_change, d.price_last_change_pct,
    d.price_close, d.price_close_change, d.price_close_change_pct,
    d.trade_date, d.created_at, d.updated_at,
    COALESCE(f.adj_factor, 1) AS adj_factor,
    d.price_first     * COALESCE(f.adj_factor, 1) AS price_first_adj,
    d.price_max       * COALESCE(f.adj_factor, 1) AS price_max_adj,
    d.price_min       * COALESCE(f.adj_factor, 1) AS price_min_adj,
    d.price_last      * COALESCE(f.adj_factor, 1) AS price_last_adj,
    d.price_close     * COALESCE(f.adj_factor, 1) AS price_close_adj,
    d.price_yesterday * COALESCE(f.adj_factor, 1) AS price_yesterday_adj
FROM daily_history d
LEFT JOIN daily_adjust_factors f
       ON f.symbol_id = d.symbol_id AND f.trade_date = d.trade_date
"""

_VIEW_SQL = f"""
CREATE VIEW {_VIEW} AS
SELECT
    h.id,
    s.id                                          AS symbol_id,
    h.symbol,
    -- ── the TRUE trade date, in both calendars ──
    jalali_to_gregorian(h.date)                   AS trade_date,
    h.date                                        AS trade_date_shamsi,
    h.time                                        AS trade_time,
    -- fetch-date column kept for traceability only
    h.gregorian_date                              AS fetch_date,
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
    h.updated_at,
    COALESCE(f.adj_factor, 1)                     AS adj_factor,
    h.price_first     * COALESCE(f.adj_factor, 1) AS price_first_adj,
    h.price_max       * COALESCE(f.adj_factor, 1) AS price_max_adj,
    h.price_min       * COALESCE(f.adj_factor, 1) AS price_min_adj,
    h.price_last      * COALESCE(f.adj_factor, 1) AS price_last_adj,
    h.price_close     * COALESCE(f.adj_factor, 1) AS price_close_adj,
    h.price_yesterday * COALESCE(f.adj_factor, 1) AS price_yesterday_adj
FROM brsapi_historical_daily h
LEFT JOIN symbols s ON s.symbol = h.symbol
LEFT JOIN daily_adjust_factors f
       ON f.symbol_id = s.id
      AND f.trade_date = jalali_to_gregorian(h.date)
"""


def upgrade() -> None:
    op.execute(_FN)
    # column set changes (renames + new columns), so REPLACE is not allowed
    op.execute(f"DROP VIEW IF EXISTS {_VIEW}")
    op.execute(_VIEW_SQL)


def downgrade() -> None:
    op.execute(f"DROP VIEW IF EXISTS {_VIEW}")
    op.execute(_VIEW_0108)
    op.execute("DROP FUNCTION IF EXISTS jalali_to_gregorian(text)")
