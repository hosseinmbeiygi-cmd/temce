#!/usr/bin/env python
"""Create generated_strategies and generation_batches tables if missing."""
import asyncio
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from sqlalchemy import text

import core.database as _db

STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS generated_strategies (
        id VARCHAR(50) PRIMARY KEY,
        symbol VARCHAR(50) NOT NULL,
        entry_indicator VARCHAR(50),
        entry_params TEXT,
        entry_condition VARCHAR(50),
        exit_indicator VARCHAR(50),
        exit_params TEXT,
        exit_condition VARCHAR(50),
        filter1_indicator VARCHAR(50),
        filter1_params TEXT,
        filter1_condition VARCHAR(50),
        filter2_indicator VARCHAR(50),
        filter2_params TEXT,
        filter2_condition VARCHAR(50),
        stop_loss_pct DOUBLE PRECISION,
        take_profit_pct DOUBLE PRECISION,
        trailing_stop VARCHAR(5),
        sizing_method VARCHAR(20),
        sizing_value DOUBLE PRECISION,
        total_return_pct DOUBLE PRECISION,
        annualized_return_pct DOUBLE PRECISION,
        sharpe_ratio DOUBLE PRECISION,
        sortino_ratio DOUBLE PRECISION,
        calmar_ratio DOUBLE PRECISION,
        max_drawdown_pct DOUBLE PRECISION,
        win_rate DOUBLE PRECISION,
        profit_factor DOUBLE PRECISION,
        total_trades INTEGER,
        winning_trades INTEGER,
        losing_trades INTEGER,
        score DOUBLE PRECISION NOT NULL,
        strategy_type VARCHAR(50),
        batch_id VARCHAR(50),
        status VARCHAR(20) DEFAULT 'active',
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_gs_symbol ON generated_strategies (symbol)",
    "CREATE INDEX IF NOT EXISTS idx_gs_score ON generated_strategies (score DESC)",
    "CREATE INDEX IF NOT EXISTS idx_gs_entry ON generated_strategies (entry_indicator)",
    "CREATE INDEX IF NOT EXISTS idx_gs_exit ON generated_strategies (exit_indicator)",
    "CREATE INDEX IF NOT EXISTS idx_gs_sharpe ON generated_strategies (sharpe_ratio DESC)",
    "CREATE INDEX IF NOT EXISTS idx_gs_batch ON generated_strategies (batch_id)",
    "CREATE INDEX IF NOT EXISTS idx_gs_status ON generated_strategies (status)",
    """CREATE TABLE IF NOT EXISTS generation_batches (
        id VARCHAR(50) PRIMARY KEY,
        symbols TEXT,
        total_configs INTEGER,
        pre_filtered INTEGER,
        tested INTEGER,
        passed_filter INTEGER,
        saved_to_db INTEGER,
        status VARCHAR(20) DEFAULT 'queued',
        started_at TIMESTAMP,
        completed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
]


async def main():
    await _db.init_database()
    async with _db.async_session_factory() as sess:
        async with sess.begin():
            for stmt in STATEMENTS:
                await sess.execute(text(stmt))
        print("Tables created successfully.")

    async with _db.async_session_factory() as sess:
        r = await sess.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'generated_strategies')"
        ))
        print("generated_strategies exists:", r.scalar())
        r2 = await sess.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'generation_batches')"
        ))
        print("generation_batches exists:", r2.scalar())


asyncio.run(main())
