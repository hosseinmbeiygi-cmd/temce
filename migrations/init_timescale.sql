-- Initialize TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ============================================================
-- Hypertables for time-series market data
-- ============================================================

-- trade_ticks: high-frequency trade data partitioned by fetched_at
SELECT create_hypertable(
    'trade_ticks',
    'fetched_at',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE,
    migrate_data => TRUE
);

-- Enable compression on trade_ticks (after 7 days)
ALTER TABLE trade_ticks SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instrument_id',
    timescaledb.compress_orderby = 'fetched_at DESC'
);
SELECT add_compression_policy('trade_ticks', INTERVAL '7 days', if_not_exists => TRUE);

-- daily_ohlcv: daily OHLCV data partitioned by trade_date (YYYYMMDD integer)
SELECT create_hypertable(
    'daily_ohlcv',
    'trade_date',
    chunk_time_interval => 1,
    if_not_exists => TRUE,
    migrate_data => TRUE
);

-- Enable compression on daily_ohlcv (after 30 days)
ALTER TABLE daily_ohlcv SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instrument_id',
    timescaledb.compress_orderby = 'trade_date DESC'
);
SELECT add_compression_policy('daily_ohlcv', INTERVAL '30 days', if_not_exists => TRUE);

-- market_snapshots: periodic market snapshots partitioned by fetched_at
SELECT create_hypertable(
    'market_snapshots',
    'fetched_at',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE,
    migrate_data => TRUE
);

-- orderbook_events: orderbook level snapshots partitioned by fetched_at
SELECT create_hypertable(
    'orderbook_events',
    'fetched_at',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE,
    migrate_data => TRUE
);
