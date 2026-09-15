"""Classify the NAV-sync failures: which instruments do they actually belong to?"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\Iran\Desktop\temce")

from sqlalchemy import text

from core.database import get_session

FAILED = [
    line.strip()
    for line in Path(r"C:\Users\Iran\Desktop\temce\_nav_failed_tmp.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if line.strip()
]
OK_SAMPLE = ["آتش", "آبنوس", "ابتکار", "اتوکار", "اهرم", "توان"]


async def main() -> None:
    async for session in get_session():
        rows = await session.execute(
            text(
                "SELECT symbol, name, sector, ins_id FROM brsapi_symbol_snapshots "
                "WHERE symbol = ANY(:x) GROUP BY symbol, name, sector, ins_id"
            ),
            {"x": FAILED + OK_SAMPLE},
        )
        data: dict[str, tuple[str, str, str]] = {}
        for sym, name, sector, ins_id in rows:
            data.setdefault(sym, (name, sector, str(ins_id)))

        print("=== FAILED (HTTP 502 on /Tsetmc/Nav) ===")
        for sym in FAILED:
            name, sector, ins_id = data.get(sym, ("<not in snapshots>", "", ""))
            print(f"{sym:>14} | {name} | {sector} | ins_id={ins_id}")
        print("\n=== OK sample ===")
        for sym in OK_SAMPLE:
            name, sector, ins_id = data.get(sym, ("<not in snapshots>", "", ""))
            print(f"{sym:>14} | {name} | {sector} | ins_id={ins_id}")

        # How many fund-sector symbols are NOT in the ETF market ("قابل معامله")?
        rows = await session.execute(
            text(
                "SELECT sector, count(DISTINCT symbol) FROM brsapi_symbol_snapshots "
                "WHERE sector ~ 'صندوق' GROUP BY sector ORDER BY 2 DESC"
            )
        )
        print("\n=== sectors containing 'صندوق' ===")
        for sector, count in rows:
            print(f"{count:>6}  {sector}")


if __name__ == "__main__":
    asyncio.run(main())
