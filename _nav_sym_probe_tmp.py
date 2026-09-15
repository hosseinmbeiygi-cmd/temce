"""Inspect DB metadata for fund symbols that BrsApi NAV rejects with 502."""

import asyncio
import sys

sys.path.insert(0, r"C:\Users\Iran\Desktop\temce")

from sqlalchemy import text

from core.database import get_session

TARGETS = ["ابتکار", "ابتکار2", "آرمانی", "آسا2", "ارکیده2", "آتی1", "ارزش2"]


async def main() -> None:
    async for session in get_session():
        rows = await session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'brsapi_symbol_snapshots' ORDER BY ordinal_position"
            ),
        )
        print("snapshot columns:", [r[0] for r in rows])

        rows = await session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name LIKE '%nav%' ORDER BY table_name, ordinal_position"
            ),
        )
        print("nav columns     :", [r[0] for r in rows])

        rows = await session.execute(
            text(
                "SELECT symbol, ins_id, sector, name FROM brsapi_symbol_snapshots "
                "WHERE symbol = ANY(:syms)"
            ),
            {"syms": TARGETS},
        )
        snapshot_rows = list(rows)
        found = {r[0] for r in snapshot_rows}
        for r in snapshot_rows:
            print(f"snapshot  {r[0]!r:>12} ins_id={r[1]} sector={r[2]!r} name={r[3]!r}")
        missing = [s for s in TARGETS if s not in found]
        print("not in brsapi_symbol_snapshots:", missing)

        rows = await session.execute(
            text(
                "SELECT symbol, ins_id, date FROM brsapi_nav_records "
                "WHERE symbol = ANY(:syms) ORDER BY symbol, date DESC LIMIT 20"
            ),
            {"syms": TARGETS},
        )
        for r in rows:
            print(f"nav       {r[0]!r:>12} ins_id={r[1]} last_date={r[2]}")


if __name__ == "__main__":
    asyncio.run(main())
