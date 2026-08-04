import sys

sys.path.insert(0, ".")
import asyncio


async def main():
    from core.database import init_database
    await init_database()
    from sqlalchemy import text

    from core.database import async_session_factory
    from core.db_utils import safe_row_str
    async with async_session_factory() as s:
        # Sample with correct columns
        r = await s.execute(text("""
            SELECT symbol, company_name, report_type, period, audit_status, publish_date, summary, attachment_url
            FROM codal_reports
            WHERE summary IS NOT NULL AND summary != ''
            LIMIT 3
        """))
        print("=== Sample codal_reports ===")
        for row in r.fetchall():
            print(f"\n  Symbol: {row[0]} | Company: {row[1]}")
            print(f"  Type: {row[2]} | Period: {row[3]} | Audit: {row[4]}")
            print(f"  Date: {row[5]}")
            print(f"  Summary: {safe_row_str(row, idx=6)[:300]}")
            print(f"  URL: {safe_row_str(row, idx=7)[:100]}")

        # All codal-related tables
        r2 = await s.execute(text("""
            SELECT tablename FROM pg_tables WHERE schemaname='public'
            AND (tablename LIKE '%codal%' OR tablename LIKE '%financial%' OR tablename LIKE '%audit%')
            ORDER BY tablename
        """))
        tables = [row[0] for row in r2.fetchall()]
        print(f"\n=== Codal-related tables ({len(tables)}) ===")
        for tbl in tables:
            try:
                r3 = await s.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
                cnt = r3.scalar()
                r4 = await s.execute(text(f"""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = '{tbl}' ORDER BY ordinal_position
                """))
                cols = [row[0] for row in r4.fetchall()]
                print(f"  {tbl}: {cnt} rows | {cols}")
            except Exception as e:
                print(f"  {tbl}: ERROR - {e}")

asyncio.run(main())
