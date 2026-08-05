"""Resumable full-archive Codal backfill that respects BrsApi quota.

BrsApi quota (AIO package):
    - max 500 requests per 5-minute window
    - max 10,000 requests per calendar day (Tehran time)

The RateLimiter (brsapi/rate_limiter.py) enforces BOTH limits globally for
every request that goes through BrsApiClient.fetch(). When the daily quota is
exhausted, acquire() blocks until Tehran midnight — so this script can simply
keep running in the background and it will auto-resume the next day.

Checkpointing: the last successfully processed page is written to a JSON file
so the archive sync can be resumed after a crash/reboot without re-processing
pages (each page is also idempotent thanks to ON CONFLICT DO NOTHING).

Usage:
    python scripts/sync_codal_backfill.py --start 1 [--checkpoint scripts/.codal_checkpoint.json]
    python scripts/sync_codal_backfill.py --until 1405-04-14   # backfill last month
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import sys
import time
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

DEFAULT_CHECKPOINT = Path(__file__).resolve().parent / ".codal_checkpoint.json"


def load_checkpoint(path: Path) -> int:
    """Return the last page already processed (1 if none)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return int(data.get("last_page", 1))
    except Exception:
        return 1


def save_checkpoint(path: Path, page: int) -> None:
    # Store page + 1 so a resume starts at the NEXT unprocessed page instead of
    # re-fetching the one just completed (fetch is idempotent either way).
    try:
        path.write_text(
            json.dumps({"last_page": page + 1, "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"  ⚠️ checkpoint save failed: {e}", flush=True)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Resumable full Codal archive backfill")
    parser.add_argument("--start", type=int, default=1, help="First page (default: 1 or checkpoint)")
    parser.add_argument("--checkpoint", type=str, default=str(DEFAULT_CHECKPOINT),
                        help="Path to checkpoint JSON file")
    parser.add_argument("--until", type=str, default=None,
                        help="Jalali cutoff YYYY-MM-DD (e.g. 1405-04-14). Stop once all "
                             "announcements on a page are older than this date.")
    args = parser.parse_args()

    cp_path = Path(args.checkpoint)
    start_page = args.start if args.start > 1 else load_checkpoint(cp_path)
    print(f"═══ Codal backfill — starting at page {start_page} "
          f"(until={args.until or 'END'}) ═══", flush=True)

    import core.database as db
    from brsapi.client import get_client
    from brsapi.services.sync_service import BrsApiSyncService

    await db.init_database()
    client = await get_client()
    svc = BrsApiSyncService(client=client)

    # sync_codal(start_page=..., backfill=True) walks page-by-page; the client
    # RateLimiter enforces the 500/5min + 10k/day quota (blocking on exhaustion).
    # on_page_processed persists a checkpoint after every page so a crash/reboot
    # resumes from the last processed page instead of page 1.
    async with db.async_session_factory() as session:
        t0 = time.monotonic()
        last_saved = start_page

        async def _checkpoint(page: int, _inserted: int) -> None:
            nonlocal last_saved
            last_saved = page
            save_checkpoint(cp_path, page)

        report = await svc.sync_codal(
            session,
            backfill=True,
            start_page=start_page,
            on_page_processed=_checkpoint,
            stop_date=args.until,
        )
        elapsed = time.monotonic() - t0

    print(f"\n═══ Done — success={report.success} items={report.items_count} "
          f"({elapsed/60:.1f} min) ═══", flush=True)
    if not report.success:
        print(f"Error: {report.error}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", flush=True)
        sys.exit(130)
