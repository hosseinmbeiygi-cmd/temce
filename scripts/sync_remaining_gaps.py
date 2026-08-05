"""Sync the remaining gaps after the bulk sync:

1. Codal announcements — continue the incremental sync (API was down with 502
   after the symbol varchar(50) fix; now back up). Incremental mode stops as
   soon as a full page is all duplicates.
2. Gold/currency/crypto DAILY history — backfill from 1405-05-01 up to today
   (was stuck because date_end was hardcoded to 1405-05-01).

Usage:
    python scripts/sync_remaining_gaps.py
"""

from __future__ import annotations

import asyncio
import io
import sys
import time
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TODAY = "1405-05-14"  # Jalali today


async def main() -> None:
    import core.database as db
    from brsapi.client import get_client
    from brsapi.services.history_fetch_service import HistoryFetchService
    from brsapi.services.sync_service import BrsApiSyncService

    await db.init_database()
    client = await get_client()
    svc = BrsApiSyncService(client=client)

    async with db.async_session_factory() as session:
        # ── 1. Codal incremental (resumes from page 1; stops at existing data) ──
        print("\n═══ CODAL incremental ═══")
        t0 = time.monotonic()
        try:
            r = await svc.sync_codal(session, backfill=False)
            print(f"  Codal: success={r.success} items={r.items_count} "
                  f"({time.monotonic() - t0:.0f}s) {r.error or ''}")
        except Exception as exc:
            print(f"  Codal FAILED: {exc}")

        # ── 2. Gold/currency history to today ──
        print("\n═══ GOLD/CURRENCY daily history → today ═══")
        t0 = time.monotonic()
        try:
            hsvc = HistoryFetchService(session=session)
            reports = await hsvc.sync_gold_currency_history(date_end=TODAY)
            ok = sum(1 for rp in reports if rp.success and rp.record_count > 0)
            rows = sum(rp.record_count for rp in reports)
            errs = [rp.symbol for rp in reports if not rp.success]
            print(f"  gold/currency: {ok}/{len(reports)} ok, {rows} rows "
                  f"({time.monotonic() - t0:.0f}s) errors={errs[:5]}")
        except Exception as exc:
            print(f"  gold/currency FAILED: {exc}")

        # ── 3. Crypto history to today ──
        print("\n═══ CRYPTO daily history → today ═══")
        t0 = time.monotonic()
        try:
            hsvc = HistoryFetchService(session=session)
            reports = await hsvc.sync_crypto_history(date_end=TODAY)
            ok = sum(1 for rp in reports if rp.success and rp.record_count > 0)
            rows = sum(rp.record_count for rp in reports)
            errs = [rp.symbol for rp in reports if not rp.success]
            print(f"  crypto: {ok}/{len(reports)} ok, {rows} rows "
                  f"({time.monotonic() - t0:.0f}s) errors={errs[:5]}")
        except Exception as exc:
            print(f"  crypto FAILED: {exc}")

    print("\n═══ DONE ═══")


if __name__ == "__main__":
    asyncio.run(main())
