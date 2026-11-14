#!/usr/bin/env python
"""Direct psycopg2 migration with Jalali date conversion."""
import sqlite3
import logging
from datetime import datetime, date
from pathlib import Path

import psycopg2
from persiantools.jdatetime import JalaliDate

from core.config import get_settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

settings = get_settings()


def migrate():
    sqlite_path = Path(__file__).parent.parent / "transactions.db"
    if not sqlite_path.exists():
        logger.warning(f"Not found: {sqlite_path}")
        return

    # Parse PostgreSQL URL
    from urllib.parse import urlparse
    parsed = urlparse(settings.database_url)
    pg_user = parsed.username
    pg_pass = parsed.password
    pg_host = parsed.hostname
    pg_port = parsed.port or 5432
    pg_db = parsed.path.lstrip('/')

    # Connect to both DBs
    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.row_factory = sqlite3.Row

    pg_conn = psycopg2.connect(
        host=pg_host, port=pg_port, database=pg_db,
        user=pg_user, password=pg_pass
    )
    pg_cursor = pg_conn.cursor()

    # Count
    sqlite_cur = sqlite_conn.cursor()
    sqlite_cur.execute("SELECT COUNT(*) FROM transactions")
    total = sqlite_cur.fetchone()[0]
    logger.info(f"SQLite: {total:,} rows")

    # Migrate in batches
    batch_size = 50000
    inserted = 0

    sqlite_cur.execute("""
        SELECT symbol, trade_date, seq_no, time, volume, price, is_canceled
        FROM transactions ORDER BY trade_date, symbol, seq_no
    """)

    insert_sql = """
        INSERT INTO transactions
        (symbol, trade_date, seq_no, time, volume, price, is_canceled)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (symbol, trade_date, seq_no) DO NOTHING
    """

    while True:
        rows = sqlite_cur.fetchmany(batch_size)
        if not rows:
            break

        # Parse Jalali dates and insert
        for row in rows:
            # Convert Jalali (شمسی) to Gregorian
            jdate = JalaliDate.parse(row['trade_date'])
            gregorian_date = jdate.to_gregorian()

            pg_cursor.execute(insert_sql, (
                row['symbol'],
                gregorian_date,
                row['seq_no'],
                row['time'],
                row['volume'],
                row['price'],
                row['is_canceled'],
            ))

        inserted += len(rows)
        pg_conn.commit()

        if inserted % 100000 == 0:
            logger.info(f"Progress: {inserted:,} / {total:,}")

    pg_cursor.execute("SELECT COUNT(*) FROM transactions")
    final = pg_cursor.fetchone()[0]
    logger.info(f"PostgreSQL: {final:,} rows (inserted {inserted:,})")

    sqlite_conn.close()
    pg_cursor.close()
    pg_conn.close()


if __name__ == "__main__":
    migrate()
