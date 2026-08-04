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
        # Sample summary content
        r = await s.execute(text("""
            SELECT symbol, title, summary, report_type, period, publish_date, attachment_url
            FROM codal_reports
            WHERE summary IS NOT NULL AND summary != ''
            LIMIT 5
        """))
        print("=== Sample codal_reports (with summary) ===")
        for row in r.fetchall():
            print(f"\n  Symbol: {row[0]}")
            print(f"  Title: {row[1][:80] if row[1] else 'N/A'}")
            print(f"  Type: {row[4]} / {row[3]}")
            print(f"  Date: {row[5]}")
            print(f"  URL: {row[6][:80] if row[6] else 'N/A'}")
            print(f"  Summary: {safe_row_str(row, idx=2)[:200]}")

        # Check codal_audit_summary and codal_financial_statements
        for tbl in ['codal_audit_summary', 'codal_financial_statements']:
            try:
                r2 = await s.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
                cnt = r2.scalar()
                print(f"\n{tbl}: {cnt} rows")
                r3 = await s.execute(text(f"""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = '{tbl}' ORDER BY ordinal_position
                """))
                cols = [row[0] for row in r3.fetchall()]
                print(f"  Columns: {cols}")
                if cnt > 0:
                    r4 = await s.execute(text(f"SELECT * FROM {tbl} LIMIT 1"))
                    row = r4.fetchone()
                    if row:
                        print(f"  Sample: {dict(zip(cols, row, strict=False))}")
            except Exception as e:
                print(f"\n{tbl}: {e}")

asyncio.run(main())
