#!/usr/bin/env python3
"""
BrsApi Scheduler Runner
=======================
Standalone script that starts the APScheduler with all BrsApi sync jobs.

This script runs the same scheduler that starts inside the API process
(``apps/api/app.py`` → ``apps/scheduler/app.py``), but as a standalone
process. Useful when:
- You want the scheduler to run independently from the API
- You deploy via Windows Task Scheduler
- You want to run sync jobs without starting the full API

Usage:
    python scripts/start_scheduler.py          # Run in foreground
    python scripts/start_scheduler.py --daemon # Run as daemon (detached)

On Windows:
    python scripts/start_scheduler.py          # Keep console open
    Or use Windows Task Scheduler to run silently in background.

Scheduled jobs (every 2-5 min):
    - brsapi_all_symbols       → TSETMC symbols (prices/volumes)
    - brsapi_index              → TSE main index
    - brsapi_index_farabours    → Farabours index
    - brsapi_options            → TSETMC option contracts
    - brsapi_ime_futures/options/certificates/funds
    - brsapi_commodities        → Global commodity prices
    - brsapi_crypto             → Cryptocurrency prices
    - brsapi_gold_currency      → Gold, currency & crypto (Gold_Currency.php)
    - brsapi_gold_currency_pro  → Pro prices (Gold_Currency_Pro.php)
    - brsapi_codal              → Codal announcements (every 15 min)
    - brsapi_full_update        → Per-symbol NAV, detail, history (every 2 hours)

Legacy sync jobs:
    - SyncQuotesJob             → Every 2 min
    - SyncSnapshotsToQuotesJob  → Every 2 min
    - NewsIngestionJob          → Every 10 min
    - SyncInstrumentsJob        → Every 24 hours
    - SyncCodalJob              → Every 6 hours
    - BackfillHistoricalDataJob → Daily at 2 AM
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import contextlib

from core.database import close_database, get_session, init_database
from core.logging import get_logger

logger = get_logger(__name__)


async def _startup_sync() -> None:
    """Optional: run a full sync on startup."""
    try:
        from brsapi.client import get_client
        from brsapi.services.sync_service import BrsApiSyncService

        logger.info("Running startup sync...")
        client = await get_client()
        async for session in get_session():
            svc = BrsApiSyncService(client=client)
            reports = await svc.sync_all(session)

            ok = sum(1 for r in reports if r.success)
            fail = sum(1 for r in reports if not r.success)
            total_items = sum(r.items_count for r in reports)
            logger.info(
                "Startup sync complete: %d OK, %d failed, %d items",
                ok, fail, total_items,
            )
            break
        await client.stop()
    except Exception:
        logger.warning("Startup sync skipped (optional)", exc_info=True)


async def main() -> None:
    import signal

    from apps.scheduler.app import SchedulerApp

    # ── Initialize database ──
    try:
        await init_database()
        logger.info("Database initialized")
    except Exception as e:
        logger.error("Database init failed: %s — scheduler will not start", e)
        sys.exit(1)

    # ── Create and start scheduler ──
    app = SchedulerApp()
    app.start()

    # ── Optional: run startup sync ──
    if "--startup-sync" in sys.argv:
        asyncio.create_task(_startup_sync())

    logger.info("=" * 60)
    logger.info("  BrsApi Scheduler is RUNNING")
    logger.info("  Press Ctrl+C to stop")
    logger.info("=" * 60)

    # ── Handle graceful shutdown ──
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Received shutdown signal, stopping scheduler...")
        app.scheduler.shutdown(wait=False)
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _signal_handler)

    # ── Wait until stopped ──
    try:
        await stop_event.wait()
    except asyncio.CancelledError:
        pass
    finally:
        await close_database()
        logger.info("Scheduler stopped. Goodbye!")


if __name__ == "__main__":
    # ── Windows console fix for emoji ──
    if sys.platform == "win32":
        with contextlib.suppress(Exception):
            sys.stdout.reconfigure(encoding="utf-8")

    # ── Daemon mode (background) ──
    if "--daemon" in sys.argv:
        if sys.platform == "win32":
            logger.warning("Daemon mode not supported on Windows. Use Windows Task Scheduler instead.")
        else:
            pid = os.fork()
            if pid > 0:
                print(f"Scheduler started in background (PID: {pid})")
                sys.exit(0)

    asyncio.run(main())
