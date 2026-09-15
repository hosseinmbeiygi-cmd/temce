"""Dump snapshot rows for selected symbols (DB only)."""

import asyncio
import sys

sys.path.insert(0, r"C:\Users\Iran\Desktop\temce")

from sqlalchemy import text

from core.database import get_session

TARGETS = [
    "آرمانی",
    "آرمانی2",
    "آرمانی4",
    "ابتکار",
    "ابتکار2",
    "آتی",
    "آتی1",
    "آتیه ملت",
    "آتیه ملت4",
]


async def main() -> None:
    async for session in get_session():
        cols = await session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'brsapi_symbol_snapshots' ORDER BY ordinal_position"
            )
        )
        print("columns:", [c[0] for c in cols])
        rows = await session.execute(
            text(
                "SELECT symbol, ins_id, name, sector, created_at, updated_at "
                "FROM brsapi_symbol_snapshots WHERE symbol = ANY(:x) "
                "ORDER BY symbol"
            ),
            {"x": TARGETS},
        )
        for r in rows:
            print(f"{r[0]!r:>16} ins_id={r[1]} name={r[2]!r} sector={r[3]!r} c={r[4]} u={r[5]}")
        nav = await session.execute(
            text(
                "SELECT symbol, date, ins_id FROM brsapi_nav_records "
                "WHERE symbol = ANY(:x) ORDER BY symbol, date DESC LIMIT 12"
            ),
            {"x": TARGETS},
        )
        for r in nav:
            print(f"naV {r[0]!r:>16} date={r[1]} ins_id={r[2]}")
        counts = await session.execute(
            text(
                "SELECT count(*) FILTER (WHERE symbol ~ '[0-9]$') AS suffixed, "
                "count(*) FILTER (WHERE symbol !~ '[0-9]$') AS plain "
                "FROM (SELECT DISTINCT symbol FROM brsapi_nav_records) t"
            )
        )
        print("nav symbol shapes:", counts.mappings().first())


if __name__ == "__main__":
    asyncio.run(main())
