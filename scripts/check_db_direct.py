"""List all tables and row counts using direct psycopg2 connection.

Credentials come from settings.database_url (DATABASE_URL in .env) — no
hardcoded passwords in the script.
"""
import contextlib
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import psycopg2  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

# Ensure project root on sys.path
PROJECT_ROOT = str(__import__("pathlib").Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.config import settings  # noqa: E402


def _connect():
    url = make_url(settings.database_url_async)
    return psycopg2.connect(
        host=url.host,
        port=url.port or 5432,
        dbname=url.database,
        user=url.username,
        password=url.password,
    )


conn = _connect()
cur = conn.cursor()

cur.execute(
    "SELECT table_name FROM information_schema.tables "
    "WHERE table_schema='public' ORDER BY table_name"
)
tables = [row[0] for row in cur.fetchall()]

print()
print("=" * 65)
print(f"{'Table Name':<40s} {'Rows':>12s}")
print("=" * 65)

for tbl in tables:
    try:
        cur.execute(f'SELECT COUNT(*) FROM "{tbl}"')
        cnt = cur.fetchone()[0] or 0
        flag = "[DATA]" if cnt > 0 else "[---]"
        print(f"  {flag} {tbl:<38s} {cnt:>12,}")
    except Exception as e:
        print(f"  [ERR]  {tbl:<38s} {str(e)[:40]}")

# Also check column details for key trade tables
for tbl in ["trades", "brsapi_intraday_trades", "quotes", "brsapi_historical_daily"]:
    with contextlib.suppress(Exception):
        cur.execute(f"""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name='{tbl}'
            ORDER BY ordinal_position
        """)
        cols = cur.fetchall()
        print(f"\n  Columns for '{tbl}':")
        for col_name, col_type in cols:
            print(f"    - {col_name} ({col_type})")

cur.close()
conn.close()
