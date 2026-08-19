-- ============================================================================
--  View definitions for legacy table migration
--  These are the SAME views created by the Alembic migration
--  (0034_deprecate_old_tables_create_views), provided here as standalone SQL
--  for reference / manual execution.
-- ============================================================================

-- ── Run order ───────────────────────────────────────────────────────────────
--  1. python scripts/backfill_dates.py    (creates trade_date_utc columns)
--  2. alembic upgrade head                (runs the migration below)
--  3. python scripts/apply_unique_indexes.py (optional: dedup + unique index)
--
--  Manual rollback:
--    DROP VIEW IF EXISTS daily_history CASCADE;
--    DROP VIEW IF EXISTS symbol_snapshots CASCADE;
--    DROP VIEW IF EXISTS intraday_trades CASCADE;
--    DROP VIEW IF EXISTS candlesticks CASCADE;
--    DROP VIEW IF EXISTS codal_announcements CASCADE;
--    ALTER TABLE daily_history_deprecated RENAME TO daily_history;
--    ALTER TABLE symbol_snapshots_deprecated RENAME TO symbol_snapshots;
--    ALTER TABLE intraday_trades_deprecated RENAME TO intraday_trades;
--    ALTER TABLE candlesticks_deprecated RENAME TO candlesticks;
--    ALTER TABLE codal_announcements_deprecated RENAME TO codal_announcements;
-- ============================================================================


-- ── 1. daily_history ────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW daily_history AS
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
LEFT JOIN symbols s ON s.symbol = h.symbol;


-- ── 2. symbol_snapshots ─────────────────────────────────────────────────────
CREATE OR REPLACE VIEW symbol_snapshots AS
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
LEFT JOIN symbols sym ON sym.symbol = s.symbol;


-- ── 3. intraday_trades ──────────────────────────────────────────────────────
-- ⚠ WARNING: old table has 9.1 M rows vs new table 1.6 M.
--    UNION ALL preserves all data until the backfill catches up.
CREATE OR REPLACE VIEW intraday_trades AS
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
    id, symbol_id, symbol, trade_date, time,
    volume, price, created_at, gregorian_date, shamsi_date
FROM intraday_trades_deprecated;


-- ── 4. candlesticks ─────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW candlesticks AS
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
LEFT JOIN symbols sym ON sym.symbol = c.symbol;


-- ── 5. codal_announcements ──────────────────────────────────────────────────
CREATE OR REPLACE VIEW codal_announcements AS
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
LEFT JOIN symbols sym ON sym.symbol = ca.symbol;