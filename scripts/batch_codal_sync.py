"""
Batch Codal Sync — fetch announcements for ALL symbols
======================================================

Loops through every unique symbol in ``brsapi_symbol_snapshots``,
fetches Codal announcements from BrsApi (with ``l18`` param), and stores
them in ``brsapi_codal_announcements`` with ``ins_id`` and ``instrument_id``.

Rate-limited to 20 req/min (3-second delay between requests).
Supports resume via a JSON checkpoint file.

Usage:
    python scripts/batch_codal_sync.py
    python scripts/batch_codal_sync.py --limit 100          # First 100 symbols only
    python scripts/batch_codal_sync.py --resume              # Resume from checkpoint
    python scripts/batch_codal_sync.py --reset               # Clear checkpoint & start fresh
    python scripts/batch_codal_sync.py --min-wait 1.5        # Faster: 1.5s delay (40 req/min)
"""

from __future__ import annotations

# --- auto PYTHONPATH ---
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import argparse
import asyncio
import contextlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ── Config ─────────────────────────────────────────────────────

CHECKPOINT_FILE = _PROJECT_ROOT / "data" / "codal_batch_checkpoint.json"
BATCH_SIZE = 50           # Commit progress every N symbols
RATE_LIMIT_DELAY = 3.0    # Seconds between requests (20 req/min)
MAX_RETRY_SAME = 3        # Max consecutive failures before pausing
MAX_RETRY_CYCLES = 10      # Max retry cycles (30 failures) before aborting

# ── Imports ────────────────────────────────────────────────────

from sqlalchemy import String, select
from sqlalchemy import column as sa_column
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from brsapi.client import BrsApiClient, get_client
from brsapi.config import BrsApiEndpoints
from brsapi.models import SymbolSnapshotModel
from brsapi.models.codal import CodalAnnouncementModel
from brsapi.parsers import CodalParser
from brsapi.repositories import BulkUpsertRepository
from core.config import settings

# ── Helpers ────────────────────────────────────────────────────


def _now_str() -> str:
    return datetime.now(UTC).strftime("%H:%M:%S")


def _load_checkpoint() -> dict[str, Any]:
    """Load checkpoint file — returns dict with ``completed``, ``last_symbol``, ``stats``."""
    if CHECKPOINT_FILE.exists():
        with contextlib.suppress(Exception), open(CHECKPOINT_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"completed": [], "last_symbol": None, "stats": {"fetched": 0, "stored": 0, "errors": 0, "no_data": 0}}


def _save_checkpoint(cp: dict[str, Any]) -> None:
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CHECKPOINT_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cp, f, ensure_ascii=False, indent=2)
    tmp.replace(CHECKPOINT_FILE)


# ── Sync one symbol ────────────────────────────────────────────


async def _sync_one(
    session: AsyncSession,
    client: BrsApiClient,
    symbol: str,
) -> dict[str, Any]:
    """
    Fetch Codal announcements for a single symbol from BrsApi and store in DB.

    Returns a result dict::
        {"symbol": str, "success": bool, "count": int, "stored": int, "error": str | None}
    """
    result: dict[str, Any] = {"symbol": symbol, "success": False, "count": 0, "stored": 0, "error": None}

    try:
        # 1. Fetch from BrsApi
        api_result = await client.fetch(
            BrsApiEndpoints.CODAL_ANNOUNCEMENT,
            params={"l18": symbol, "page": "1"},
        )

        if not api_result.success:
            result["error"] = api_result.error or "API fetch failed"
            return result

        # 2. Parse
        records = CodalParser.parse_announcements_only(api_result.value.data)
        result["count"] = len(records)

        if not records:
            result["success"] = True  # Empty is not an error
            result["error"] = "no_data"
            return result

        # 3. Lookup ins_id + instrument_id from snapshots
        stmt = select(
            SymbolSnapshotModel.symbol,
            SymbolSnapshotModel.ins_id,
            SymbolSnapshotModel.instrument_id,
        ).where(SymbolSnapshotModel.symbol == symbol)
        snap = await session.execute(stmt)
        snap_row = snap.one_or_none()

        ins_id = str(snap_row.ins_id) if snap_row and snap_row.ins_id else None
        instrument_id = str(snap_row.instrument_id) if snap_row and snap_row.instrument_id else None

        # Fallback to instruments table
        if not instrument_id:
            with contextlib.suppress(Exception):
                fb = await session.execute(
                    select(sa_column("id", String))
                    .select_from(sa_text("instruments"))
                    .where(sa_column("symbol", String) == symbol)
                )
                fb_row = fb.scalar_one_or_none()
                if fb_row:
                    instrument_id = str(fb_row)

        # 4. Attach ids
        for r in records:
            if ins_id:
                r["ins_id"] = ins_id
            if instrument_id:
                r["instrument_id"] = instrument_id

        # 5. Store in DB (retry without FK fields if needed)
        repo = BulkUpsertRepository(session, CodalAnnouncementModel)
        try:
            result["stored"] = await repo.bulk_insert(records)
            await session.commit()
            result["success"] = True
        except Exception:
            await session.rollback()
            # Retry without FK fields
            for r in records:
                r.pop("ins_id", None)
                r.pop("instrument_id", None)
            try:
                result["stored"] = await repo.bulk_insert(records)
                await session.commit()
                result["success"] = True
            except Exception:
                await session.rollback()
                result["error"] = "DB insert failed (both attempts)"
                result["stored"] = 0

    except Exception as exc:
        result["error"] = str(exc)

    return result


# ── Main loop ──────────────────────────────────────────────────


async def main() -> None:

    parser = argparse.ArgumentParser(description="Batch Codal sync for all symbols")
    parser.add_argument("--limit", type=int, default=0, help="Only process first N symbols")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--reset", action="store_true", help="Clear checkpoint and start fresh")
    parser.add_argument("--min-wait", type=float, default=RATE_LIMIT_DELAY, help=f"Min delay between requests (default: {RATE_LIMIT_DELAY}s)")
    args = parser.parse_args()

    delay = max(0.5, args.min_wait)

    # Load / reset checkpoint
    cp = _load_checkpoint()
    if args.reset:
        cp = {"completed": [], "last_symbol": None, "stats": {"fetched": 0, "stored": 0, "errors": 0, "no_data": 0}}
        print("Checkpoint reset.")
    elif args.resume:
        print(f"Resuming from checkpoint — {len(cp['completed'])} symbols already done.")
    else:
        cp = {"completed": [], "last_symbol": None, "stats": {"fetched": 0, "stored": 0, "errors": 0, "no_data": 0}}

    done_set = set(cp["completed"])

    # Database
    db_url = settings.database_url
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    print(f"[{_now_str()}] Connecting to database...")
    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Get all unique symbols, sorted by trade_value descending
        print(f"[{_now_str()}] Fetching symbols from database...")
        stmt = (
            select(SymbolSnapshotModel.symbol)
            .where(SymbolSnapshotModel.symbol.isnot(None))
            .where(SymbolSnapshotModel.symbol != "")
            .distinct()
            .order_by(SymbolSnapshotModel.trade_value.desc().nullslast())
        )
        result = await session.execute(stmt)
        all_symbols = [row[0] for row in result if row[0]]

        total = len(all_symbols)
        print(f"[{_now_str()}] Found {total} unique symbols.")

        if args.limit > 0:
            all_symbols = all_symbols[: args.limit]
            total = len(all_symbols)
            print(f"  Limited to {total} symbols.")

        # Filter out already-completed
        remaining = [s for s in all_symbols if s not in done_set]
        skipped = total - len(remaining)
        if skipped:
            print(f"  Skipping {skipped} already-completed symbols.")

        if not remaining:
            print("No symbols to process!")
            await engine.dispose()
            return

        # Init client
        print(f"[{_now_str()}] Initializing BrsApi client...")
        client = await get_client()

        print(f"\n{'='*60}")
        print(f"  Starting batch Codal sync — {len(remaining)} symbols")
        print(f"  Rate limit: 1 req / {delay}s ({int(60/delay)} req/min)")
        print(f"  Est. time: {len(remaining) * delay / 60:.0f} minutes")
        print(f"{'='*60}\n")

        start_time = time.monotonic()
        consecutive_failures = 0
        retry_cycles = 0

        for idx, symbol in enumerate(remaining):
            progress_pct = (idx + 1) / len(remaining) * 100

            # Rate limit
            if idx > 0:
                await asyncio.sleep(delay)

            # Sync
            req_start = time.monotonic()
            res = await _sync_one(session, client, symbol)
            req_ms = (time.monotonic() - req_start) * 1000

            # Update stats
            cp["stats"]["fetched"] += 1
            if res["stored"] > 0:
                cp["stats"]["stored"] += res["stored"]

            if res["success"] and res["count"] == 0:
                cp["stats"]["no_data"] += 1
                status = "empty"
            elif res["success"]:
                status = f"stored {res['stored']}"
                consecutive_failures = 0
            else:
                cp["stats"]["errors"] += 1
                status = f"FAIL ({res['error'][:40]})"
                consecutive_failures += 1

            # Mark completed
            cp["completed"].append(symbol)
            cp["last_symbol"] = symbol

            # Progress line
            elapsed = time.monotonic() - start_time
            rate = (idx + 1) / elapsed if elapsed > 0 else 0
            remaining_time = (len(remaining) - idx - 1) / rate if rate > 0 else 0

            eta_m = int(remaining_time // 60)
            eta_s = int(remaining_time % 60)

            print(
                f"  [{progress_pct:5.1f}%] "
                f"[{_now_str()}] "
                f"{symbol:<20s} "
                f"count={res['count']:<3d} "
                f"{status:<20s} "
                f"{req_ms:6.0f}ms "
                f"ETA {eta_m:02d}:{eta_s:02d}"
            )

            # Periodic checkpoint save
            if (idx + 1) % BATCH_SIZE == 0:
                _save_checkpoint(cp)
                s = cp["stats"]
                print(
                    f"  ── CHECKPOINT saved. "
                    f"Fetched {s['fetched']} | Stored {s['stored']} | "
                    f"NoData {s['no_data']} | Errors {s['errors']} ──"
                )

            # Check for too many consecutive failures
            if consecutive_failures >= MAX_RETRY_SAME:
                retry_cycles += 1
                if retry_cycles >= MAX_RETRY_CYCLES:
                    print(
                        f"  🔴 ABORTING after {retry_cycles} retry cycles "
                        f"({consecutive_failures} consecutive failures). "
                        f"API may be down."
                    )
                    break
                print(
                    f"  ⚠️  {consecutive_failures} consecutive failures. "
                    f"Waiting 30s (cycle {retry_cycles}/{MAX_RETRY_CYCLES})..."
                )
                await asyncio.sleep(30)
                consecutive_failures = 0

        # Save final checkpoint
        _save_checkpoint(cp)

        total_elapsed = time.monotonic() - start_time
        s = cp["stats"]
        print(f"\n{'='*60}")
        print("  COMPLETE!")
        print(f"  Total time: {total_elapsed / 60:.1f} minutes")
        print(f"  Symbols processed: {len(remaining)}")
        print(f"  Total fetched: {s['fetched']}")
        print(f"  Total stored in DB: {s['stored']}")
        print(f"  No data (empty): {s['no_data']}")
        print(f"  Errors: {s['errors']}")
        print(f"{'='*60}")

    await engine.dispose()
    print(f"\n[{_now_str()}] Done!")


if __name__ == "__main__":
    asyncio.run(main())
