#!/usr/bin/env python
from __future__ import annotations

# --- auto PYTHONPATH ---
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

from core.logging import get_logger

logger = get_logger(__name__)


def create_schema() -> None:
    schema_sql = """
-- Iran Market Platform - SQL Server Schema

CREATE TABLE instruments (
    id NVARCHAR(50) PRIMARY KEY,
    symbol NVARCHAR(50) NOT NULL,
    name NVARCHAR(200),
    isin NVARCHAR(50),
    market_type NVARCHAR(20),
    asset_class NVARCHAR(20),
    status NVARCHAR(20) DEFAULT 'active',
    sector_code NVARCHAR(20),
    group_code NVARCHAR(20),
    tick_size FLOAT DEFAULT 1.0,
    lot_size INT DEFAULT 1,
    par_value INT DEFAULT 1000,
    eps FLOAT DEFAULT 0,
    shares_count BIGINT DEFAULT 0,
    base_volume BIGINT DEFAULT 0,
    exchange_code NVARCHAR(20),
    board_code NVARCHAR(20),
    data_source NVARCHAR(20) DEFAULT 'tsetmc',
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    updated_at DATETIME2
);

CREATE TABLE quotes (
    id NVARCHAR(50) PRIMARY KEY,
    instrument_id NVARCHAR(50) REFERENCES instruments(id),
    symbol NVARCHAR(50),
    price_close FLOAT, price_open FLOAT, price_high FLOAT, price_low FLOAT,
    price_last FLOAT, price_change FLOAT, price_change_pct FLOAT,
    volume BIGINT, value FLOAT, trade_count INT,
    price_yesterday FLOAT, ask_price FLOAT, ask_volume INT,
    bid_price FLOAT, bid_volume INT,
    time NVARCHAR(20), date NVARCHAR(20),
    timeframe NVARCHAR(10) DEFAULT '1d',
    data_source NVARCHAR(20) DEFAULT 'tsetmc',
    created_at DATETIME2 DEFAULT GETUTCDATE()
);
"""
    logger.info("SQL Server schema SQL generated.")
    print(schema_sql)


if __name__ == "__main__":
    create_schema()
