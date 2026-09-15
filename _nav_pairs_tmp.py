"""Check suffixed-vs-base name equality for fund symbols (DB only)."""

import asyncio
import re
import sys

sys.path.insert(0, r"C:\Users\Iran\Desktop\temce")

from sqlalchemy import text

from core.database import get_session

SUFFIX = re.compile(r"[0-9]+$")


async def main() -> None:
    async for session in get_session():
        rows = await session.execute(
            text(
                "SELECT symbol, name, sector FROM brsapi_symbol_snapshots "
                "WHERE sector LIKE '%صندوق%' AND sector NOT LIKE '%بیمه%' "
                "AND sector NOT LIKE '%بازنشستگی%' GROUP BY symbol, name, sector"
            )
        )
        info: dict[str, set[tuple[str, str]]] = {}
        for sym, name, sector in rows:
            info.setdefault(sym, set()).add((name, sector))

        plain = {s for s in info if not SUFFIX.search(s)}
        suffixed = [s for s in info if SUFFIX.search(s)]

        same_name = 0
        diff_name: list[tuple[str, str]] = []
        no_base: list[str] = []
        multi_name = 0
        for sym in sorted(suffixed):
            base = SUFFIX.sub("", sym)
            if base not in plain:
                no_base.append(sym)
                continue
            base_names = {n for n, _ in info[base]}
            sym_names = {n for n, _ in info[sym]}
            if len(sym_names) > 1:
                multi_name += 1
            if base_names == sym_names:
                same_name += 1
            else:
                diff_name.append((sym, sorted(sym_names | base_names)[:2].__str__()))

        print(f"plain fund symbols      : {len(plain)}")
        print(f"suffixed fund symbols   : {len(suffixed)}")
        print(f"  base name identical   : {same_name}")
        print(f"  base name different   : {len(diff_name)}")
        print(f"  no plain base in DB   : {len(no_base)} -> {no_base[:10]}")
        print(f"  suffixed w/ >1 name   : {multi_name}")
        for row in diff_name[:10]:
            print("   diff:", row)

        # Distinct digit suffixes actually used
        tails: dict[str, int] = {}
        for sym in suffixed:
            tails[SUFFIX.search(sym).group(0)] = tails.get(SUFFIX.search(sym).group(0), 0) + 1
        print("suffix histogram:", dict(sorted(tails.items())))

if __name__ == "__main__":
    asyncio.run(main())
