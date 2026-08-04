#!/usr/bin/env python
"""Fix NULL market values in brsapi_symbol_details using ISIN from symbol_snapshots.

ISIN rules:
  IROF... → فرابورس
  IRO...  → بورس
  Other   → leave as NULL (can't determine)
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import settings

UPDATE_SQL = text("""
    UPDATE brsapi_symbol_details d
    SET market = :market,
        updated_at = NOW()
    FROM brsapi_symbol_snapshots s
    WHERE d.ins_id = s.ins_id
      AND (d.market IS NULL OR d.market = '')
      AND s.isin IS NOT NULL AND s.isin != ''
      AND (
        (s.isin LIKE 'IROF%%' AND :market = 'فرابورس')
        OR
        (s.isin LIKE 'IRO%%' AND s.isin NOT LIKE 'IROF%%' AND :market = 'بورس')
      )
""")

CHECK_SQL = text("""
    SELECT
        d.ins_id, d.symbol, d.isin, s.isin as snap_isin,
        d.sector, d.board
    FROM brsapi_symbol_details d
    JOIN brsapi_symbol_snapshots s ON d.ins_id = s.ins_id
    WHERE (d.market IS NULL OR d.market = '')
      AND s.isin IS NOT NULL AND s.isin != ''
    ORDER BY d.symbol
    LIMIT 50
""")

async def main():
    engine = create_async_engine(settings.database_url_async, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        # 1. Show records to fix
        print(">>> Records with NULL market (preview):")
        result = await session.execute(CHECK_SQL)
        rows = result.fetchall()
        if not rows:
            print("    No NULL market records found!")
        else:
            for r in rows:
                isin = r.snap_isin or ""
                market_guess = ""
                if isin.startswith("IROF"):
                    market_guess = "فرابورس"
                elif isin.startswith("IRO"):
                    market_guess = "بورس"
                print(f"    {r.symbol:10s}  ins_id={r.ins_id:15s}  ISIN={isin:30s}  → {market_guess}")

            if rows:
                print(f"\nTotal NULL market records: {len(rows)}")

        # 2. If there are records, ask user and fix
        if rows:
            print("\n>>> Fixing...")
            # Fix فرابورس first
            result1 = await session.execute(UPDATE_SQL, {"market": "فرابورس"})
            fixed1 = result1.rowcount
            print(f"    Set فرابورس: {fixed1} rows")

            # Fix بورس
            result2 = await session.execute(UPDATE_SQL, {"market": "بورس"})
            fixed2 = result2.rowcount
            print(f"    Set بورس: {fixed2} rows")

            await session.commit()
            print(f"\n    ✅ Total fixed: {fixed1 + fixed2} rows")
        else:
            print("\n    ✅ Nothing to fix — all market fields are populated!")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
