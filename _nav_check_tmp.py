"""Inspect NAV rows written by the smoke run."""

import asyncio
import sys

sys.path.insert(0, r"C:\Users\Iran\Desktop\temce")

from sqlalchemy import text

from core.database import get_session


async def main() -> None:
    async for session in get_session():
        rows = await session.execute(
            text(
                "SELECT symbol, date, ins_id, created_at FROM brsapi_nav_records "
                "WHERE symbol = ANY(:x) ORDER BY symbol, date DESC, created_at DESC"
            ),
            {"x": ["ابتکار", "آبنوس"]},
        )
        for r in rows:
            print(f"{r[0]!r:>12} date={r[1]} ins_id={r[2]} created={r[3]}")
        dupes = await session.execute(
            text(
                "SELECT symbol, date, count(*) c FROM brsapi_nav_records "
                "GROUP BY symbol, date HAVING count(*) > 1 ORDER BY c DESC LIMIT 10"
            )
        )
        print("\nduplicate (symbol, date) groups:", [tuple(r) for r in dupes])
        total = await session.execute(
            text("SELECT count(*), max(date) FROM brsapi_nav_records")
        )
        print("nav total / max date:", total.first())
        uniq = await session.execute(
            text("SELECT count(DISTINCT symbol) FROM brsapi_nav_records WHERE date = '1405-06-22'")
        )
        print("symbols with 1405-06-22:", uniq.scalar())


if __name__ == "__main__":
    asyncio.run(main())
