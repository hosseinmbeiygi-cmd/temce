#!/usr/bin/env python
"""
Migrate historical transactions from SQLite (transactions.db) to PostgreSQL.
Run this after Alembic migration 0125 creates the transactions table.

Usage:
    python scripts/migrate_transactions_sqlite_to_pg.py
"""
import sqlite3
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from core.config import get_settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

settings = get_settings()


async def migrate_transactions():
    """Read from SQLite, write to PostgreSQL in batches."""

    sqlite_path = Path(__file__).parent.parent / "transactions.db"
    if not sqlite_path.exists():
        logger.warning(f"SQLite DB not found at {sqlite_path}")
        return

    # Open AsyncPG connection pool
    engine = create_async_engine(
        settings.database_url_async,
        echo=False,
        pool_size=5,
    )

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        # Connect to SQLite (synchronous)
        sqlite_conn = sqlite3.connect(str(sqlite_path))
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_cur = sqlite_conn.cursor()

        # Count total rows
        sqlite_cur.execute("SELECT COUNT(*) FROM transactions")
        total_rows = sqlite_cur.fetchone()[0]
        logger.info(f"Total rows in SQLite: {total_rows:,}")

        # Batch insert
        batch_size = 5000
        inserted = 0

        sqlite_cur.execute("""
            SELECT symbol, trade_date, seq_no, time, volume, price, is_canceled
            FROM transactions
            ORDER BY trade_date, symbol, seq_no
        """)

        async with async_session() as session:
            while True:
                rows = sqlite_cur.fetchmany(batch_size)
                if not rows:
                    break

                # Build INSERT statement
                values = [
                    {
                        "symbol": row[0],
                        "trade_date": row[1],
                        "seq_no": row[2],
                        "time": row[3],
                        "volume": row[4],
                        "price": row[5],
                        "is_canceled": row[6],
                    }
                    for row in rows
                ]

                stmt = text("""
                    INSERT INTO transactions
                    (symbol, trade_date, seq_no, time, volume, price, is_canceled)
                    VALUES
                    (:symbol, :trade_date, :seq_no, :time, :volume, :price, :is_canceled)
                    ON CONFLICT (symbol, trade_date, seq_no) DO NOTHING
                """)

                await session.execute(stmt, values)
                inserted += len(rows)

                if inserted % 50000 == 0:
                    logger.info(f"Inserted {inserted:,} / {total_rows:,} rows")

            await session.commit()

        sqlite_cur.close()
        sqlite_conn.close()

        logger.info(f"Migration complete: {inserted:,} rows inserted")

        # Verify
        async with async_session() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM transactions"))
            final_count = result.scalar()
            logger.info(f"Verification: {final_count:,} rows in PostgreSQL")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate_transactions())
