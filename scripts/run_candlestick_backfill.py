"""Manual runner for the full-market candlestick backfill.

Runs ``brsapi_candlesticks_all`` logic directly (same code path as the
daily job / manage API) with an overridable chunk size, so an admin can
kick off a larger backfill without the scheduler or the API server.

Usage::

    python scripts/run_candlestick_backfill.py [--max-symbols 500] [--sleep 11]

Designed to be launched detached::

    nohup python scripts/run_candlestick_backfill.py --max-symbols 500 > candle_backfill.log 2>&1 &
"""

from __future__ import annotations

import argparse
import asyncio
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _log(msg: str) -> None:
    print(msg, flush=True)


async def main(max_symbols: int, sleep_s: float | None) -> None:
    from brsapi.client import get_client
    from brsapi.config import settings as brsapi_settings
    from brsapi.jobs.registry import get_brsapi_job_registry
    from brsapi.services.sync_service import BrsApiSyncService
    from core.database import get_session

    chunk = max_symbols if max_symbols > 0 else brsapi_settings.candle_daily_max_symbols
    _log(f"Starting manual candlestick backfill — chunk={chunk} sleep={sleep_s or brsapi_settings.candle_req_delay}s")

    client = await get_client()
    registry = get_brsapi_job_registry()

    async for session in get_session():
        service = BrsApiSyncService(client=client, session=session)
        report = await registry._run_candlesticks_all(
            session,
            service,
            max_symbols=chunk,
            sleep_s=sleep_s,
            allow_weekend=True,   # manual run — never blocked by the weekend guard
        )
        if report is None:
            _log("FAILED: no symbols found / aborted")
            break
        _log(f"DONE: success={report.success} items={report.items_count} "
             f"duration_ms={report.duration_ms:.0f} error={report.error}")
        break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manual full-market candlestick backfill")
    parser.add_argument("--max-symbols", type=int, default=0,
                        help="Chunk size (0 = settings default; e.g. 500 for a larger run)")
    parser.add_argument("--sleep", type=float, default=None,
                        help="Seconds between API requests (default from settings, 11s)")
    args = parser.parse_args()
    asyncio.run(main(args.max_symbols, args.sleep))
