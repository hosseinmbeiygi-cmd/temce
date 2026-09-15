"""Diagnostics: fund-symbol discovery stats for NAV sync (DB only, no network)."""

import asyncio
import re
import sys

sys.path.insert(0, r"C:\Users\Iran\Desktop\temce")

from sqlalchemy import text

from core.database import get_session

DIGIT_SUFFIX = re.compile(r"[0-9]+\s*$")


async def main() -> None:
    async for session in get_session():
        rows = await session.execute(
            text(
                "SELECT count(*) AS total, "
                "count(*) FILTER (WHERE sector ~ '[0-9]') AS sector_with_digit "
                "FROM brsapi_symbol_snapshots"
            )
        )
        print("snapshots:", rows.mappings().first())

        rows = await session.execute(
            text(
                "SELECT DISTINCT sector FROM brsapi_symbol_snapshots "
                "WHERE sector LIKE '%صندوق%' ORDER BY 1"
            )
        )
        sectors = [r[0] for r in rows]
        print(f"\nfund-ish sectors ({len(sectors)}):")
        for s in sectors:
            print("   ", s)

        rows = await session.execute(
            text(
                "SELECT symbol FROM brsapi_symbol_snapshots "
                "WHERE sector LIKE '%صندوق%' AND sector NOT LIKE '%بیمه%' "
                "AND sector NOT LIKE '%بازنشستگی%' GROUP BY symbol ORDER BY symbol"
            )
        )
        fund_symbols = [r[0] for r in rows]
        with_digit = [s for s in fund_symbols if DIGIT_SUFFIX.search(s or "")]
        without_digit = [s for s in fund_symbols if not DIGIT_SUFFIX.search(s or "")]
        print(f"\nfund symbols: {len(fund_symbols)}")
        print(f"  numeric suffix: {len(with_digit)}")
        print(f"  no suffix     : {len(without_digit)}")

        rows = await session.execute(
            text(
                "SELECT symbol, name, sector FROM brsapi_symbol_snapshots "
                "WHERE symbol = ANY(:syms)"
            ),
            {"syms": with_digit[:25]},
        )
        print("\nsample suffixed rows:")
        for r in rows:
            print(f"   {r[0]!r:>18} name={r[1]!r} sector={r[2]!r}")

        # how many suffixed symbols have a matching base symbol in snapshots?
        bases = {DIGIT_SUFFIX.sub("", s) for s in with_digit} - set(without_digit)
        print(f"\nbase symbols missing from non-suffixed set: {len(bases)}")
        print("  sample:", sorted(bases)[:20])

        # suffixed symbols that are NOT resolvable to a known base
        rows = await session.execute(
            text(
                "SELECT count(DISTINCT symbol) FROM brsapi_symbol_snapshots "
                "WHERE symbol = ANY(:syms)"
            ),
            {"syms": sorted(bases)[:200]},
        )
        print("  of those, present as their own snapshot:", rows.scalar())

        rows = await session.execute(
            text(
                "SELECT COUNT(*) FROM brsapi_nav_records"
            )
        )
        print("\nnav rows:", rows.scalar())
        rows = await session.execute(
            text("SELECT DISTINCT symbol FROM brsapi_nav_records ORDER BY 1 LIMIT 30")
        )
        print("nav symbols sample:", [r[0] for r in rows])


if __name__ == "__main__":
    asyncio.run(main())
