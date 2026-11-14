#!/usr/bin/env python
"""
Migrate historical transactions from SQLite (transactions.db) to PostgreSQL.
Run this after Alembic migration 0125 creates the transactions table.

Usage:
    python scripts/migrate_transactions_sqlite_to_pg.py
"""
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text

from core.config import get_settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

settings = get_settings()


def migrate_transactions():
    """Read from SQLite, write to PostgreSQL in batches."""

    sqlite_path = Path(__file__).parent.parent / "transactions.db"
    if not sqlite_path.exists():
        logger.warning(f"SQLite DB not found at {sqlite_path}")
        return

    # Sync engine (simpler for large batch insert)
    db_url_sync = settings.database_url.replace('postgresql+asyncpg', 'postgresql')
    engine = create_engine(db_url_sync, echo=False, pool_size=3)

    try:
        # Connect to SQLite
        sqlite_conn = sqlite3.connect(str(sqlite_path))
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_cur = sqlite_conn.cursor()

        # Count total rows
        sqlite_cur.execute("SELECT COUNT(*) FROM transactions")
        total_rows = sqlite_cur.fetchone()[0]
        logger.info(f"Total rows in SQLite: {total_rows:,}")

        # Batch insert
        batch_size = 10000
        inserted = 0

        sqlite_cur.execute("""
            SELECT symbol, trade_date, seq_no, time, volume, price, is_canceled
            FROM transactions
            ORDER BY trade_date, symbol, seq_no
        """)

        with engine.begin() as conn:
            while True:
                rows = sqlite_cur.fetchmany(batch_size)
                if not rows:
                    break

                # Convert to tuples with parsed dates
                data = []
                for row in rows:
                    trade_date = datetime.strptime(row['trade_date'], "%Y-%m-%d").date()
                    data.append((
                        row['symbol'],
                        trade_date,
                        row['seq_no'],
                        row['time'],
                        row['volume'],
                        row['price'],
                        row['is_canceled'],
                    ))

                # Use raw INSERT with execute
                stmt = text("""
                    INSERT INTO transactions
                    (symbol, trade_date, seq_no, time, volume, price, is_canceled)
                    VALUES
                    (:symbol, :trade_date, :seq_no, :time, :volume, :price, :is_canceled)
                    ON CONFLICT (symbol, trade_date, seq_no) DO NOTHING
                """)

                for symbol, trade_date, seq_no, time, volume, price, is_canceled in data:
                    conn.execute(stmt, {
                        "symbol": symbol,
                        "trade_date": trade_date,
                        "seq_no": seq_no,
                        "time": time,
                        "volume": volume,
                        "price": price,
                        "is_canceled": is_canceled,
                    })

                inserted += len(data)

                if inserted % 50000 == 0:
                    logger.info(f"Inserted {inserted:,} / {total_rows:,} rows")

        sqlite_cur.close()
        sqlite_conn.close()

        logger.info(f"Migration complete: {inserted:,} rows inserted")

        # Verify
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM transactions"))
            final_count = result.scalar()
            logger.info(f"Verification: {final_count:,} rows in PostgreSQL")

    finally:
        engine.dispose()


if __name__ == "__main__":
    migrate_transactions()
