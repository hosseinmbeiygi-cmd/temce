import sys

sys.path.insert(0, ".")
import asyncio


async def main():
    from core.database import init_database
    await init_database()
    from sqlalchemy import text

    from core.database import async_session_factory
    async with async_session_factory() as s:
        r = await s.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'codal_audit_summary' ORDER BY ordinal_position
        """))
        print("codal_audit_summary columns:")
        for row in r.fetchall():
            print(f"  {row[0]}: {row[1]} (nullable={row[2]})")

asyncio.run(main())
