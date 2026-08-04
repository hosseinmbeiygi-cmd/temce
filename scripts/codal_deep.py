import json
import sys

sys.path.insert(0, ".")
import asyncio


async def main():
    from core.database import init_database
    await init_database()
    from sqlalchemy import text

    from core.database import async_session_factory
    async with async_session_factory() as s:
        # What report types exist?
        r = await s.execute(text("""
            SELECT report_type, COUNT(*) as cnt
            FROM codal_reports
            GROUP BY report_type
            ORDER BY cnt DESC
        """))
        print("=== Report types ===")
        for row in r.fetchall():
            print(f"  {row[0]}: {row[1]}")

        # Check codal_financial_statements parsed_data
        r2 = await s.execute(text("""
            SELECT symbol, title, parsed_data
            FROM codal_financial_statements
            WHERE parsed_data IS NOT NULL
            LIMIT 3
        """))
        print("\n=== codal_financial_statements samples ===")
        for row in r2.fetchall():
            print(f"\n  Symbol: {row[0]}")
            print(f"  Title: {row[1]}")
            if row[2]:
                try:
                    d = json.loads(row[2]) if isinstance(row[2], str) else row[2]
                    if isinstance(d, dict):
                        print(f"  Keys: {list(d.keys())[:10]}")
                        # Show first few values
                        for k, v in list(d.items())[:5]:
                            print(f"    {k}: {str(v)[:100]}")
                except Exception:
                    print(f"  parsed_data: {str(row[2])[:200]}")

        # Check codal_audit_summary full_results
        r3 = await s.execute(text("""
            SELECT symbol, health_score, health_classification, revenue, net_profit, eps, roe, roa
            FROM codal_audit_summary
            LIMIT 5
        """))
        print("\n=== codal_audit_summary samples ===")
        for row in r3.fetchall():
            print(f"  {row[0]}: health={row[1]} ({row[2]}) rev={row[3]} np={row[4]} eps={row[5]} roe={row[6]} roa={row[7]}")

        # How many symbols have audit data?
        r4 = await s.execute(text("SELECT COUNT(DISTINCT symbol) FROM codal_audit_summary"))
        print(f"\nSymbols with audit data: {r4.scalar()}")

        # How many symbols have financial statements?
        r5 = await s.execute(text("SELECT COUNT(DISTINCT symbol) FROM codal_financial_statements"))
        print(f"Symbols with financial statements: {r5.scalar()}")

asyncio.run(main())
