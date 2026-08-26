"""One-off check of brsapi_symbol_snapshots state."""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from sqlalchemy import create_engine, text

# Credentials come from settings/.env — never hardcode them in scripts.
try:
    from scripts._db import database_url_async
    DB_URL = database_url_async().replace("+asyncpg", "")
except Exception:  # pragma: no cover
    DB_URL = os.environ.get("DATABASE_URL", "").replace("+asyncpg", "")

ENG = create_engine(DB_URL)

with ENG.connect() as c:
    r = c.execute(text("SELECT COUNT(*) FROM brsapi_symbol_snapshots"))
    print("total rows:", r.scalar())
    r = c.execute(text("SELECT COUNT(DISTINCT symbol) FROM brsapi_symbol_snapshots"))
    print("distinct symbols:", r.scalar())

    print("--- sector distribution (distinct symbols) ---")
    r = c.execute(
        text(
            "SELECT sector, COUNT(DISTINCT symbol) c FROM brsapi_symbol_snapshots "
            "GROUP BY sector ORDER BY c DESC LIMIT 25"
        )
    )
    for row in r:
        print(row[0], "->", row[1])

    print("--- newest fetch batches ---")
    r = c.execute(
        text(
            "SELECT fetched_at, COUNT(DISTINCT symbol) FROM brsapi_symbol_snapshots "
            "GROUP BY fetched_at ORDER BY fetched_at DESC LIMIT 5"
        )
    )
    for row in r:
        print(row)

    print("--- specific symbols present? ---")
    for sym in ["موج", "فولاد", "تسه1405", "اراد1232"]:
        r = c.execute(
            text("SELECT COUNT(*) FROM brsapi_symbol_snapshots WHERE symbol = :s"),
            {"s": sym},
        )
        print(sym, "->", r.scalar())

    print("--- bonds / maskan (اوراق / تسهیلات) ---")
    r = c.execute(
        text(
            "SELECT COUNT(DISTINCT symbol) FROM brsapi_symbol_snapshots "
            "WHERE sector LIKE '%اوراق%' OR sector LIKE '%تسهیلات%'"
        )
    )
    print("bonds/maskan distinct:", r.scalar())

    print("--- instruments table count ---")
    try:
        r = c.execute(text("SELECT COUNT(*) FROM instruments"))
        print("instruments rows:", r.scalar())
    except Exception as e:
        print("instruments query err:", e)
