import json
import sys

sys.path.insert(0, ".")
import asyncio
import contextlib


async def main():
    from core.database import init_database
    await init_database()
    from sqlalchemy import text

    from core.database import async_session_factory
    async with async_session_factory() as s:
        # 1. codal_reports structure
        r = await s.execute(text("""
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_name = 'codal_reports' ORDER BY ordinal_position
        """))
        print("=== codal_reports columns ===")
        for row in r.fetchall():
            print(f"  {row[0]}: {row[1]}")

        # 2. Stats
        r2 = await s.execute(text("SELECT COUNT(*), COUNT(DISTINCT symbol) FROM codal_reports"))
        row = r2.fetchone()
        print(f"\nTotal rows: {row[0]}, Unique symbols: {row[1]}")

        # 3. Sample raw_json structure
        r3 = await s.execute(text("SELECT raw_json FROM codal_reports WHERE raw_json IS NOT NULL LIMIT 1"))
        row = r3.fetchone()
        if row and row[0]:
            try:
                data = json.loads(row[0])
                print("\n=== raw_json keys ===")
                print(json.dumps(list(data.keys()), indent=2))
                print("\n=== raw_json sample ===")
                print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
            except Exception:
                print(f"\nraw_json (first 500): {row[0][:500]}")

        # 4. Other codal tables
        r4 = await s.execute(text("""
            SELECT tablename FROM pg_tables WHERE schemaname='public'
            AND (tablename LIKE '%codal%' OR tablename LIKE '%financial%')
            ORDER BY tablename
        """))
        print("\n=== Codal-related tables ===")
        for row in r4.fetchall():
            r5 = await s.execute(text(f"SELECT COUNT(*) FROM {row[0]}"))
            print(f"  {row[0]}: {r5.scalar()} rows")

        # 5. Check codal_audit_summary
        with contextlib.suppress(Exception):
            r6 = await s.execute(text("""
                SELECT column_name, data_type FROM information_schema.columns
                WHERE table_name = 'codal_audit_summary' ORDER BY ordinal_position
            """))
            print("\n=== codal_audit_summary columns ===")
            for row in r6.fetchall():
                print(f"  {row[0]}: {row[1]}")

        # 6. Check codal_financial_statements
        with contextlib.suppress(Exception):
            r7 = await s.execute(text("""
                SELECT column_name, data_type FROM information_schema.columns
                WHERE table_name = 'codal_financial_statements' ORDER BY ordinal_position
            """))
            print("\n=== codal_financial_statements columns ===")
            for row in r7.fetchall():
                print(f"  {row[0]}: {row[1]}")

asyncio.run(main())
