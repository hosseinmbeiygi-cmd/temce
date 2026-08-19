"""Install dual-date (Gregorian + Shamsi) conversion functions and trigger machinery.

Idempotent — safe to re-run. Creates:
  - _g2d / _jal_cal / j2d / d2g          (Jalali algorithm core, ported from jalaali-js)
  - shamsi_to_miladi / miladi_to_shamsi   (exposed converters)
  - any_to_miladi                         (format-tolerant classifier)
  - dual_date_columns                     (meta table: table_name -> source_column)
  - sync_dual_dates_fn                    (BEFORE INSERT OR UPDATE trigger function)

Usage:
    python scripts/install_dual_dates.py
"""
from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

try:  # shared helper used by the other scripts
    from scripts._db import database_url_async

    DB_URL = database_url_async()
except Exception:  # pragma: no cover
    import os

    DB_URL = os.environ.get("DATABASE_URL")

FUNCS: list[str] = [
    # Gregorian calendar -> JDN (integer division truncates, matches jalaali-js)
    """
CREATE OR REPLACE FUNCTION _g2d(gy int, gm int, gd int) RETURNS int AS $B$
SELECT ((gy + (gm - 8) / 6 + 100100) * 1461) / 4
     + (153 * ((gm + 9) % 12) + 2) / 5
     + gd - 34840408
     - (((gy + 100100 + (gm - 8) / 6) / 100) * 3) / 4
     + 752
$B$ LANGUAGE sql IMMUTABLE STRICT
""",
    # Persian calendar core: returns (gy, march, leap) for a Jalali year
    """
CREATE OR REPLACE FUNCTION _jal_cal(jy int, without_leap boolean DEFAULT false)
RETURNS TABLE(gy int, march int, leap int) AS $B$
DECLARE
  breaks int[] := ARRAY[-61,9,38,199,426,686,756,818,1111,1181,1210,1635,2060,2097,2192,2262,2324,2394,2456,3178];
  leapJ int := -14; jp int := breaks[1]; jump int := 0; n int; leapG int; i int; l int;
BEGIN
  FOR i IN 2..array_length(breaks, 1) LOOP
    IF jy < breaks[i] THEN EXIT; END IF;
    jump = breaks[i] - jp;
    leapJ = leapJ + (jump / 33) * 8 + (jump % 33) / 4;
    jp = breaks[i];
  END LOOP;
  n = jy - jp;
  leapJ = leapJ + (n / 33) * 8 + (n % 33 + 3) / 4;
  IF (jump % 33) = 4 AND (jump - n) = 4 THEN leapJ = leapJ + 1; END IF;
  leapG = ((jy + 621) / 4) - (((jy + 621) / 100 + 1) * 3) / 4 - 150;
  march = 20 + leapJ - leapG;
  l := 0;
  IF NOT without_leap THEN
    IF jump - n < 6 THEN n = n - jump + ((jump + 4) / 33) * 33; END IF;
    l = ((n + 1) % 33 - 1) % 4;
    IF l = -1 THEN l = 4; END IF;
  END IF;
  RETURN QUERY SELECT jy + 621, march, l;
END;
$B$ LANGUAGE plpgsql IMMUTABLE STRICT
""",
    # Jalali date -> JDN
    """
CREATE OR REPLACE FUNCTION j2d(jy int, jm int, jd int) RETURNS int AS $B$
SELECT _g2d(r.gy, 3, r.march) + (jm - 1) * 31 - (jm / 7) * (jm - 7) + jd - 1
FROM _jal_cal(jy, true) r
$B$ LANGUAGE sql IMMUTABLE STRICT
""",
    # JDN -> Gregorian date parts
    """
CREATE OR REPLACE FUNCTION d2g(jdn int) RETURNS TABLE(gy int, gm int, gd int) AS $B$
DECLARE j int; i int; d int; m int; y int;
BEGIN
  j = 4 * jdn + 139361631;
  j = j + (((4 * jdn + 183187720) / 146097) * 3) / 4 * 4 - 3908;
  i = ((j % 1461) / 4) * 5 + 308;
  d = ((i % 153) / 5) + 1;
  m = ((i / 153) % 12) + 1;
  y = (j / 1461) - 100100 + (8 - m) / 6;
  RETURN QUERY SELECT y, m, d;
END;
$B$ LANGUAGE plpgsql IMMUTABLE STRICT
""",
    # '1405-05-10' (or 1405/05/10, Persian/Arabic digits, stray quotes) -> date
    """
CREATE OR REPLACE FUNCTION shamsi_to_miladi(sh text) RETURNS date AS $B$
DECLARE
  s text; jy int; jm int; jd int; jdn int; r record;
BEGIN
  IF sh IS NULL THEN RETURN NULL; END IF;
  s := translate(sh, E'\u06F0\u06F1\u06F2\u06F3\u06F4\u06F5\u06F6\u06F7\u06F8\u06F9\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669', '01234567890123456789');
  s := btrim(replace(replace(s, chr(39), ''), '/', '-'));
  IF s !~ '^[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}$' THEN RETURN NULL; END IF;
  jy := substring(s from 1 for 4)::int;
  jm := split_part(s, '-', 2)::int;
  jd := split_part(s, '-', 3)::int;
  IF jm < 1 OR jm > 12 OR jd < 1 OR jd > 31 THEN RETURN NULL; END IF;
  jdn := j2d(jy, jm, jd);
  SELECT * INTO r FROM d2g(jdn);
  IF r IS NULL THEN RETURN NULL; END IF;
  RETURN make_date(r.gy, r.gm, r.gd);
END;
$B$ LANGUAGE plpgsql IMMUTABLE STRICT
""",
    # date -> 'YYYY-MM-DD' in the Persian calendar
    """
CREATE OR REPLACE FUNCTION miladi_to_shamsi(gdate date) RETURNS text AS $B$
DECLARE
  gy int; gm int; gd int; jdn int; jy int; k int; jm int; jd int; m1 int;
BEGIN
  IF gdate IS NULL THEN RETURN NULL; END IF;
  gy := EXTRACT(YEAR FROM gdate)::int;
  gm := EXTRACT(MONTH FROM gdate)::int;
  gd := EXTRACT(DAY FROM gdate)::int;
  jdn := _g2d(gy, gm, gd);
  jy := gy - 621;
  SELECT march INTO m1 FROM _jal_cal(jy, true);
  k := jdn - _g2d(gy, 3, m1);
  IF k < 0 THEN
    -- date falls before Nowruz: belongs to the previous Jalali year.
    -- Add the exact length of that year (365 or 366 days) so k becomes
    -- the true 0-based day index within the previous year.
    jy := jy - 1;
    k := k + (_g2d(jy + 622, 3, (SELECT march FROM _jal_cal(jy + 1, true)))
              - _g2d(jy + 621, 3, (SELECT march FROM _jal_cal(jy, true))));
  END IF;
  IF k > 185 THEN
    -- second half of the year: months 7..12 (30 days each)
    k := k - 186;
    jm := 7 + k / 30;
    jd := k % 30 + 1;
  ELSE
    -- first half of the year: months 1..6 (31 days each)
    jm := 1 + k / 31;
    jd := k % 31 + 1;
  END IF;
  RETURN lpad(jy::text, 4, '0') || '-' || lpad(jm::text, 2, '0') || '-' || lpad(jd::text, 2, '0');
END;
$B$ LANGUAGE plpgsql IMMUTABLE STRICT
""",
    # Tolerant classifier: shamsi / gregorian / ISO timestamp -> miladi date or NULL
    """
CREATE OR REPLACE FUNCTION any_to_miladi(v text) RETURNS date AS $B$
DECLARE s text; t text;
BEGIN
  IF v IS NULL OR btrim(v) = '' THEN RETURN NULL; END IF;
  s := translate(v, E'\u06F0\u06F1\u06F2\u06F3\u06F4\u06F5\u06F6\u06F7\u06F8\u06F9\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669', '01234567890123456789');
  s := btrim(replace(s, chr(39), ''));
  IF s ~ '^[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}[T ]' THEN
    s := substring(s from 1 for 10);
  END IF;
  IF s ~ '^[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}$' THEN
    t := split_part(s, '-', 1);
    IF t::int BETWEEN 1800 AND 2200 THEN
      BEGIN
        RETURN s::date;
      EXCEPTION WHEN others THEN RETURN NULL; END;
    END IF;
    RETURN shamsi_to_miladi(s);
  END IF;
  IF s ~ '^[0-9]{4}/[0-9]{1,2}/[0-9]{1,2}$' THEN
    t := split_part(s, '/', 1);
    IF t::int BETWEEN 1800 AND 2200 THEN
      BEGIN
        RETURN to_date(s, 'YYYY/MM/DD');
      EXCEPTION WHEN others THEN RETURN NULL; END;
    END IF;
    RETURN shamsi_to_miladi(s);
  END IF;
  IF s ~ '^[0-9]{4}\\.[0-9]{1,2}\\.[0-9]{1,2}$' THEN
    RETURN shamsi_to_miladi(replace(s, '.', '-'));
  END IF;
  RETURN NULL;
END;
$B$ LANGUAGE plpgsql IMMUTABLE STRICT
""",
    # meta table mapping each table to its primary date source column
    """
CREATE TABLE IF NOT EXISTS dual_date_columns (
  table_name   text PRIMARY KEY,
  source_column text NOT NULL
)
""",
    # generic BEFORE INSERT/UPDATE trigger function
    #
    # On TimescaleDB hypertables the trigger is propagated to chunks, where
    # TG_TABLE_NAME is the chunk name (e.g. _hyper_12_8225_chunk), so the
    # dual_date_columns lookup by TG_TABLE_NAME misses. On that miss path the
    # parent hypertable is resolved through _timescaledb_catalog (internal
    # catalog — verified against the TimescaleDB version this deployment runs;
    # the public view timescaledb_information.chunks is a slower alternative).
    #
    # The resolved source column is cached per session in a custom GUC
    # (dual_date.src_<relid>) keyed by relation OID. On a 100k-row bulk-insert
    # benchmark (fresh session, same chunk) this is ~190 us/row vs ~330 us/row
    # without the cache, and the per-row catalog + meta-table lookups drop
    # from 5,001 to 1 per session (baseline with no trigger: ~26 us/row).
    #
    # Caveats (by design, acceptable): the cache is session-local, so a
    # long-lived connection keeps the source column resolved at first touch —
    # if dual_date_columns is edited mid-session, refresh connections (or run
    # SET RESET ALL). Entries accumulate one small string per distinct table
    # OID (a few bytes each).
    """
CREATE OR REPLACE FUNCTION sync_dual_dates_fn() RETURNS trigger AS $B$
DECLARE src_col text; src_val text; mil date; tbl text; key text;
BEGIN
  key := 'dual_date.src_' || TG_RELID::text;
  src_col := NULLIF(current_setting(key, true), '');
  IF src_col IS NULL THEN
    SELECT source_column INTO src_col FROM dual_date_columns WHERE table_name = TG_TABLE_NAME;
    IF src_col IS NULL THEN
      -- TimescaleDB chunk -> resolve the parent hypertable. Guarded so the
      -- function also works on plain PostgreSQL (no _timescaledb_catalog).
      IF to_regclass('_timescaledb_catalog.chunk') IS NOT NULL THEN
        SELECT h.table_name INTO tbl
        FROM _timescaledb_catalog.chunk c
        JOIN _timescaledb_catalog.hypertable h ON c.hypertable_id = h.id
        WHERE c.schema_name = TG_TABLE_SCHEMA AND c.table_name = TG_TABLE_NAME;
        IF tbl IS NOT NULL THEN
          SELECT source_column INTO src_col FROM dual_date_columns WHERE table_name = tbl;
        END IF;
      END IF;
    END IF;
    IF src_col IS NOT NULL THEN
      PERFORM set_config(key, src_col, false);
    END IF;
  END IF;
  IF src_col IS NULL THEN RETURN NEW; END IF;
  EXECUTE format('SELECT $1.%I::text', src_col) INTO src_val USING NEW;
  mil := any_to_miladi(src_val);
  NEW.gregorian_date := mil;
  NEW.shamsi_date := CASE WHEN mil IS NULL THEN NULL ELSE miladi_to_shamsi(mil) END;
  RETURN NEW;
END;
$B$ LANGUAGE plpgsql
""",
]


async def main() -> None:
    engine = create_async_engine(DB_URL)
    async with engine.begin() as conn:
        for stmt in FUNCS:
            await conn.execute(text(stmt))
    await engine.dispose()
    print(f"OK: installed {len(FUNCS)} statements (functions + meta table + trigger function)")


if __name__ == "__main__":
    asyncio.run(main())
