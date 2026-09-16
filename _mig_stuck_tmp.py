import asyncio
from core.database import init_database
from sqlalchemy import text

async def main():
    await init_database()
    from core.database import engine
    async with engine.begin() as conn:
        # Check for locks blocking DDL (migration 0046 creates materialized views etc.)
        rows = (await conn.execute(text("""
            SELECT pid, state, wait_event_type, wait_event, now()-query_start AS running_for,
                   left(query, 90) AS query
            FROM pg_stat_activity
            WHERE datname = current_database() AND pid <> pg_backend_pid()
              AND state <> 'idle'
            ORDER BY query_start
        """))).fetchall()
        for r in rows:
            print(r)
        if not rows:
            print("no blocking/stuck queries")

asyncio.run(main())
