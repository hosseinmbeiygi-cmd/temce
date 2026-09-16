import asyncio
from core.database import init_database
from sqlalchemy import text

async def main():
    await init_database()
    from core.database import engine
    # Kill the stuck migration backends (materialized view scan + blocked DDL)
    async with engine.begin() as conn:
        rows = (await conn.execute(text("""
            SELECT pid, state, wait_event_type, left(query, 60) AS q
            FROM pg_stat_activity
            WHERE datname = current_database() AND pid <> pg_backend_pid()
              AND (query ILIKE 'CREATE MATERIALIZED VIEW%' OR query ILIKE 'CREATE TABLE contracts%' OR query ILIKE '%alembic%')
        """))).fetchall()
        for r in rows:
            print("terminating:", r[0], r[2], r[3])
            await conn.execute(text(f"SELECT pg_terminate_backend({r[0]})"))
        if not rows:
            print("nothing to terminate")

asyncio.run(main())
