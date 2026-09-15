"""Live check: sector discovery + duplicate-name folding, then a 2-symbol smoke fetch."""

import asyncio
import re
import sys

sys.path.insert(0, r"C:\Users\Iran\Desktop\temce")

from brsapi.client import get_client
from brsapi.services.sync_service import (
    BrsApiSyncService,
    canonical_nav_symbol,
)
from core.database import get_session

SUFFIX = re.compile(r"[0-9]+\s*$")


async def main() -> None:
    client = await get_client()
    async for session in get_session():
        svc = BrsApiSyncService(client=client)
        raw = await svc._get_fund_symbols(session)
        print(f"discovered      : {len(raw)}")
        print(f"  suffixed      : {sum(1 for s in raw if SUFFIX.search(s))}")

        known = set(raw)
        folded = {s: canonical_nav_symbol(s, known) for s in raw}
        canonical = []
        seen = set()
        for s in raw:
            c = folded[s]
            if c not in seen:
                seen.add(c)
                canonical.append(c)
        print(f"canonical       : {len(canonical)}")
        print(f"  still suffixed: {[s for s in canonical if SUFFIX.search(s)]}")
        print(f"  head          : {canonical[:6]}")

        print("\n--- smoke: real fetch of the first 2 discovered symbols ---")
        report = await svc.sync_nav_all(session, max_symbols=2, sleep_seconds=1)
        print("success        :", report.success)
        print("items_count    :", report.items_count)
        print("skipped        :", report.skipped, report.skipped_symbols)
        print("no_data        :", report.no_data_symbols)
        print("failed         :", report.failed_symbols)
        print("normalized     :", report.normalized_symbols[:5], "...")
        print("error          :", report.error)


if __name__ == "__main__":
    asyncio.run(main())
