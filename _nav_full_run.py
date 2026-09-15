"""Full NAV batch run against the live DB + BrsApi (all fund symbols)."""

import asyncio
import logging
import sys
import time

sys.path.insert(0, r"C:\Users\Iran\Desktop\temce")

from brsapi.client import get_client
from brsapi.services.sync_service import BrsApiSyncService
from core.database import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


async def main() -> None:
    started = time.monotonic()
    client = await get_client()
    report = None
    async for session in get_session():
        svc = BrsApiSyncService(client=client)
        report = await svc.sync_nav_all(session)
    assert report is not None
    print("=" * 60)
    print("FULL NAV BATCH RESULT")
    print("elapsed_sec     :", round(time.monotonic() - started, 1))
    print("success         :", report.success)
    print("items_count     :", report.items_count)
    print("skipped         :", report.skipped)
    print("skipped_count   :", len(report.skipped_symbols))
    print("no_data_count   :", len(report.no_data_symbols))
    print("failed_count    :", len(report.failed_symbols))
    print("normalized_count:", len(report.normalized_symbols))
    print("error           :", report.error)
    print("no_data_sample  :", report.no_data_symbols[:5])
    print("failed_sample   :", report.failed_symbols[:5])


if __name__ == "__main__":
    asyncio.run(main())
