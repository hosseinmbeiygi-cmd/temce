#!/usr/bin/env python
"""Update existing transaction rows with Jalali date column."""
import sqlite3
import logging
from pathlib import Path

import psycopg2
from persiantools.jdatetime import JalaliDate

from core.config import get_settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

settings = get_settings()


def update_jalali():
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

    # Update in batches
    batch_size = 50000
    updated = 0

    sqlite_cur.execute("""
        SELECT symbol, trade_date, seq_no
        FROM transactions ORDER BY trade_date, symbol, seq_no
    """)

    update_sql = """
        UPDATE transactions
        SET trade_date_jalali = %s
        WHERE symbol = %s AND seq_no = %s
    """

    while True:
        rows = sqlite_cur.fetchmany(batch_size)
        if not rows:
            break

        # Update with Jalali dates
        for row in rows:
            jalali_str = row['trade_date']

            pg_cursor.execute(update_sql, (
                jalali_str,
                row['symbol'],
                row['seq_no'],
            ))

        updated += len(rows)
        pg_conn.commit()

        if updated % 100000 == 0:
            logger.info(f"Progress: {updated:,} / {total:,}")

    pg_cursor.execute("SELECT COUNT(*) FROM transactions WHERE trade_date_jalali IS NOT NULL")
    final = pg_cursor.fetchone()[0]
    logger.info(f"Updated: {final:,} rows with Jalali dates")

    sqlite_conn.close()
    pg_cursor.close()
    pg_conn.close()


if __name__ == "__main__":
    update_jalali()
