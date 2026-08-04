#!/usr/bin/env python
"""Check the current state of market/isin fields in symbol tables."""
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import settings


async def main():
    engine = create_async_engine(settings.database_url_async, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        # 1. SymbolDetails: check market field
        result = await session.execute(text("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN market IS NULL OR market = '' THEN 1 ELSE 0 END) as null_market,
                SUM(CASE WHEN isin IS NULL OR isin = '' THEN 1 ELSE 0 END) as null_isin
            FROM brsapi_symbol_details
        """))
        row = result.one()
        print("📊 brsapi_symbol_details:")
        print(f"   Total: {row.total}")
        print(f"   NULL market: {row.null_market} ({(row.null_market/row.total*100 if row.total else 0):.1f}%)")
        print(f"   NULL isin: {row.null_isin} ({(row.null_isin/row.total*100 if row.total else 0):.1f}%)")

        # Sample market values
        result2 = await session.execute(text("""
            SELECT market, COUNT(*) as cnt
            FROM brsapi_symbol_details
            WHERE market IS NOT NULL AND market != ''
            GROUP BY market
            ORDER BY cnt DESC
            LIMIT 20
        """))
        rows2 = result2.fetchall()
        if rows2:
            print("\n📌 Unique market values found:")
            for r in rows2:
                print(f"   '{r.market}': {r.cnt}")
        else:
            print("\n⚠️ No market values found at all!")

        # 2. SymbolSnapshots: check isin field
        result3 = await session.execute(text("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN isin IS NULL OR isin = '' THEN 1 ELSE 0 END) as null_isin
            FROM brsapi_symbol_snapshots
        """))
        row3 = result3.one()
        print("\n📊 brsapi_symbol_snapshots:")
        print(f"   Total: {row3.total}")
        print(f"   NULL isin: {row3.null_isin} ({(row3.null_isin/row3.total*100 if row3.total else 0):.1f}%)")

        # Sample ISIN prefixes
        result4 = await session.execute(text("""
            SELECT
                CASE
                    WHEN isin LIKE 'IROF%' THEN 'IROF (FaraBourse)'
                    WHEN isin LIKE 'IRO%' THEN 'IRO (Bourse)'
                    WHEN isin IS NULL OR isin = '' THEN 'NULL/Empty'
                    ELSE 'Other'
                END as isin_group,
                COUNT(*) as cnt
            FROM brsapi_symbol_snapshots
            GROUP BY isin_group
            ORDER BY cnt DESC
        """))
        rows4 = result4.fetchall()
        print("\n📌 ISIN prefix distribution:")
        for r in rows4:
            print(f"   {r.isin_group}: {r.cnt}")

        # 3. How many symbols would get market field from ISIN?
        result5 = await session.execute(text("""
            SELECT COUNT(*) as cnt
            FROM (
                SELECT s.ins_id
                FROM brsapi_symbol_snapshots s
                LEFT JOIN brsapi_symbol_details d ON s.ins_id = d.ins_id
                WHERE (d.market IS NULL OR d.market = '')
                  AND (s.isin IS NOT NULL AND s.isin != '')
            ) sub
        """))
        row5 = result5.one()
        print("\n🔧 Symbols WHERE market=NULL in details BUT isin exists in snapshots:")
        print(f"   Can fix: {row5.cnt} symbols")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
