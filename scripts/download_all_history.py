"""Bulk-download historical prices for ALL instruments from BrsApi."""

# --- auto PYTHONPATH ---
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text

from brsapi.client import get_client
from brsapi.services.sync_service import BrsApiSyncService
from core.database import close_database, get_session, init_database
from core.db_utils import safe_row_str

DOWNLOAD_ALL = False   # set True for full download, False for test


async def download_all():
    await init_database()
    total = 0
    errors = 0

    async for session in get_session():
        r = await session.execute(
            text("SELECT symbol FROM instruments ORDER BY symbol")
        )
        symbols = [safe_row_str(row, idx=0) for row in r.fetchall()]
        print(f"Total instruments: {len(symbols)}")

        # get existing symbols with history to skip
        r = await session.execute(
            text("SELECT DISTINCT symbol FROM brsapi_historical_daily")
        )
        existing_symbols = {str(row[0]) for row in r.fetchall()}
        print(f"Symbols with existing history: {len(existing_symbols)}")

        client = await get_client()
        sync_svc = BrsApiSyncService(client=client, session=session)

        limit = None if DOWNLOAD_ALL else 5
        to_download = [
            sym for sym in symbols if sym not in existing_symbols
        ][:limit]

        print(f"Symbols to download: {len(to_download)}")

        for i, symbol in enumerate(to_download, 1):
            try:
                report = await sync_svc.sync_history_price(
                    symbol=symbol, session=session
                )
                if report.success:
                    total += report.items_count
                    print(f"[{i}/{len(to_download)}] {symbol}: {report.items_count} records")
                else:
                    print(f"[{i}/{len(to_download)}] ERROR {symbol}: {report.error}", file=sys.stderr)
                    errors += 1
            except Exception as e:
                print(f"[{i}/{len(to_download)}] FAIL {symbol}: {e}", file=sys.stderr)
                errors += 1

            # rate limit: 20 req/min → 3 sec
            await asyncio.sleep(3)

        await client.aclose()
        break

    await close_database()
    print(f"\nDone. Downloaded: {total} records. Errors: {errors}")


if __name__ == "__main__":
    asyncio.run(download_all())
