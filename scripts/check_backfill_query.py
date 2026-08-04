#!/usr/bin/env python
"""Check why the backfill query returns 0 symbols."""
from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from sqlalchemy import text

from core.database import async_session_factory


async def main():
    if not async_session_factory:
        print("No DB session factory")
        return

    async with async_session_factory() as sess:
        # 1. Check instruments
        r = await sess.execute(text("SELECT COUNT(*) FROM instruments"))
        print(f"Total instruments: {r.scalar()}")

        r = await sess.execute(text("SELECT COUNT(*) FROM instruments WHERE symbol IS NOT NULL AND symbol != ''"))
        print(f"Instruments with symbol: {r.scalar()}")

        # Check if status column exists
        r = await sess.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'instruments' AND column_name = 'status'
        """))
        col = r.fetchone()
        print(f"Has 'status' column: {col is not None}")

        # Sample symbols
        r = await sess.execute(text("SELECT symbol FROM instruments WHERE symbol IS NOT NULL AND symbol != '' LIMIT 10"))
        symbols = [row[0] for row in r]
        print(f"Sample symbols: {symbols}")

        # 2. Check brsapi_historical_daily
        r = await sess.execute(text("SELECT COUNT(*) FROM brsapi_historical_daily"))
        print(f"brsapi_historical_daily rows: {r.scalar()}")

        # 3. Try backfill query with status filter
        query = """
            SELECT i.symbol
            FROM instruments i
            LEFT JOIN (
                SELECT symbol, COUNT(*) AS bar_count
                FROM brsapi_historical_daily
                WHERE price_close > 0
                GROUP BY symbol
            ) h ON i.symbol = h.symbol
            WHERE i.symbol IS NOT NULL AND i.symbol != ''
              AND (i.status IS NULL OR i.status = 'active')
              AND (h.bar_count IS NULL OR h.bar_count < 30)
            ORDER BY h.bar_count ASC NULLS FIRST, i.symbol ASC
            LIMIT 50
        """
        try:
            r = await sess.execute(text(query))
            results = r.fetchall()
            print(f"\nWith status filter: {len(results)} symbols")
            if results:
                print(f"  First 5: {[row[0] for row in results[:5]]}")
        except Exception as e:
            print(f"\nWith status filter ERROR: {e}")

        # 4. Try without status filter
        query2 = """
            SELECT i.symbol
            FROM instruments i
            LEFT JOIN (
                SELECT symbol, COUNT(*) AS bar_count
                FROM brsapi_historical_daily
                WHERE price_close > 0
                GROUP BY symbol
            ) h ON i.symbol = h.symbol
            WHERE i.symbol IS NOT NULL AND i.symbol != ''
              AND (h.bar_count IS NULL OR h.bar_count < 30)
            ORDER BY h.bar_count ASC NULLS FIRST, i.symbol ASC
            LIMIT 50
        """
        try:
            r = await sess.execute(text(query2))
            results = r.fetchall()
            print(f"\nWithout status filter: {len(results)} symbols")
            if results:
                print(f"  First 5: {[row[0] for row in results[:5]]}")
            else:
                # Try even simpler query
                r = await sess.execute(text("SELECT symbol FROM instruments WHERE symbol IS NOT NULL AND symbol != '' LIMIT 50"))
                all_syms = [row[0] for row in r]
                print(f"  All instruments: {len(all_syms)} symbols")
                print(f"  First 5: {all_syms[:5]}")
        except Exception as e:
            print(f"\nWithout status filter ERROR: {e}")

        # 5. Check what symbols are in brsapi_symbol_snapshots (used by sync_per_symbol)
        r = await sess.execute(text("SELECT COUNT(DISTINCT symbol) FROM brsapi_symbol_snapshots WHERE symbol IS NOT NULL AND symbol != ''"))
        print(f"\nSymbols in brsapi_symbol_snapshots: {r.scalar()}")

        r = await sess.execute(text("SELECT DISTINCT symbol FROM brsapi_symbol_snapshots WHERE symbol IS NOT NULL AND symbol != '' ORDER BY symbol LIMIT 10"))
        snap_syms = [row[0] for row in r]
        print(f"  First 10: {snap_syms}")


if __name__ == "__main__":
    asyncio.run(main())
