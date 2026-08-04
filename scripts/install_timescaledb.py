import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2


def main():
    from core.config import settings

    # Parse connection info from DATABASE_URL
    url = settings.database_url
    # postgresql+asyncpg://hossein:1343@localhost:5432/my_first_db
    parts = url.replace("postgresql+asyncpg://", "").split("@")
    user_pass = parts[0].split(":")
    host_db = parts[1].split("/")
    user = user_pass[0]
    password = user_pass[1]
    host = host_db[0].split(":")[0]
    port = int(host_db[0].split(":")[1]) if ":" in host_db[0] else 5432
    dbname = host_db[1]

    print(f"Connecting to {host}:{port}/{dbname} as {user}")

    conn = psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password)
    conn.autocommit = True
    cur = conn.cursor()

    # Step 1: CREATE EXTENSION
    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
        print("Step 1: CREATE EXTENSION executed!")
    except Exception as e:
        print(f"Step 1 error: {e}")
        # Try without CASCADE
        try:
            cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
            print("Step 1 (retry): CREATE EXTENSION executed without CASCADE!")
        except Exception as e2:
            print(f"Step 1 retry error: {e2}")

    # Step 2: Verify
    cur.execute("SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb'")
    row = cur.fetchone()
    if row:
        print(f"Step 2: TimescaleDB version {row[1]} installed!")
    else:
        print("Step 2: TimescaleDB NOT found")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
