-- ============================================================
-- Base schema for Iran Market Platform
-- Runs on first postgres startup via docker-entrypoint-initdb.d
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- Core Tables
-- ============================================================

-- Instruments (stocks, ETFs, bonds, etc.)
CREATE TABLE IF NOT EXISTS instruments (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    industry VARCHAR(100),
    market VARCHAR(50) DEFAULT 'main',
    isin VARCHAR(20),
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Daily OHLCV candles
CREATE TABLE IF NOT EXISTS daily_ohlcv (
    id SERIAL PRIMARY KEY,
    instrument_id INTEGER REFERENCES instruments(id),
    trade_date INTEGER NOT NULL,
    open NUMERIC(18, 2),
    high NUMERIC(18, 2),
    low NUMERIC(18, 2),
    close NUMERIC(18, 2),
    volume BIGINT,
    value NUMERIC(20, 2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(instrument_id, trade_date)
);

-- Trade ticks (high-frequency)
CREATE TABLE IF NOT EXISTS trade_ticks (
    id SERIAL PRIMARY KEY,
    instrument_id INTEGER REFERENCES instruments(id),
    price NUMERIC(18, 2),
    volume INTEGER,
    count INTEGER,
    fetched_at TIMESTAMPTZ DEFAULT NOW()
);

-- Market snapshots
CREATE TABLE IF NOT EXISTS market_snapshots (
    id SERIAL PRIMARY KEY,
    snapshot_type VARCHAR(50),
    payload JSONB,
    fetched_at TIMESTAMPTZ DEFAULT NOW()
);

-- Order book events
CREATE TABLE IF NOT EXISTS orderbook_events (
    id SERIAL PRIMARY KEY,
    instrument_id INTEGER REFERENCES instruments(id),
    bids JSONB,
    asks JSONB,
    last_price NUMERIC(18, 2),
    spread NUMERIC(18, 2),
    fetched_at TIMESTAMPTZ DEFAULT NOW()
);

-- News articles
CREATE TABLE IF NOT EXISTS news_articles (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT,
    content TEXT,
    source VARCHAR(100),
    category VARCHAR(50),
    sentiment VARCHAR(20),
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Signals
CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    instrument_id INTEGER REFERENCES instruments(id),
    signal_type VARCHAR(20) NOT NULL,
    strength NUMERIC(5, 4),
    strategy VARCHAR(100),
    confidence VARCHAR(20),
    horizon VARCHAR(50),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Backtests
CREATE TABLE IF NOT EXISTS backtests (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200),
    strategy VARCHAR(200),
    config JSONB,
    result JSONB,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Portfolios
CREATE TABLE IF NOT EXISTS portfolios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    initial_capital NUMERIC(20, 2) DEFAULT 0,
    current_value NUMERIC(20, 2) DEFAULT 0,
    currency VARCHAR(10) DEFAULT 'IRR',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Portfolio positions
CREATE TABLE IF NOT EXISTS portfolio_positions (
    id SERIAL PRIMARY KEY,
    portfolio_id UUID REFERENCES portfolios(id) ON DELETE CASCADE,
    instrument_id INTEGER REFERENCES instruments(id),
    symbol VARCHAR(20),
    quantity INTEGER DEFAULT 0,
    avg_cost NUMERIC(18, 2) DEFAULT 0,
    current_price NUMERIC(18, 2) DEFAULT 0,
    market_value NUMERIC(20, 2) DEFAULT 0,
    unrealized_pnl NUMERIC(20, 2) DEFAULT 0,
    weight_pct NUMERIC(5, 2) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Users
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(200),
    password_hash VARCHAR(500),
    role VARCHAR(50) DEFAULT 'user',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Job runs
CREATE TABLE IF NOT EXISTS job_runs (
    id SERIAL PRIMARY KEY,
    job_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'running',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error TEXT,
    metadata JSONB
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_daily_ohlcv_instrument ON daily_ohlcv(instrument_id);
CREATE INDEX IF NOT EXISTS idx_daily_ohlcv_date ON daily_ohlcv(trade_date);
CREATE INDEX IF NOT EXISTS idx_trade_ticks_instrument ON trade_ticks(instrument_id);
CREATE INDEX IF NOT EXISTS idx_trade_ticks_time ON trade_ticks(fetched_at);
CREATE INDEX IF NOT EXISTS idx_signals_instrument ON signals(instrument_id);
CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at);
CREATE INDEX IF NOT EXISTS idx_news_published ON news_articles(published_at);
