"""
Master Sync Runner
==================

One-shot script to run ALL BrsApi data syncs in 6 phases:

  Phase 1 — Bulk Market Data (AllSymbols, Index, Options, IME, etc.)
  Phase 2 — Per-Symbol Details (SymbolDetail, Candlestick, History)
  Phase 3 — Per-Symbol Transactions (ریز معاملات روزانه)
  Phase 4 — Per-Symbol Shareholders (ترکیب سهامداران)
  Phase 5 — Codal (Announcements → Download Excel → Parse → Store)
  Phase 6 — Screener Profiles (Full Populate + Free Float Update)

Usage:
    python scripts/sync_master_run.py                    # All 6 phases
    python scripts/sync_master_run.py --phases 1 3 5     # Only phases 1, 3, 5
    python scripts/sync_master_run.py --phases 6         # Only phase 6 (screener)
    python scripts/sync_master_run.py --symbols 50       # First 50 symbols only
    python scripts/sync_master_run.py --cron             # Production cron mode (skip long ops)
    python scripts/sync_master_run.py --daily-limit 3000 # Custom daily limit
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

# Ensure project root is on sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Apply network fix BEFORE any HTTP requests
from core.fix_network import fix_network

fix_network()


def _print(msg: str) -> None:
    """Unicode-safe print."""
    try:
        print(msg)
    except UnicodeEncodeError:
        safe = msg.encode("ascii", errors="replace").decode("ascii")
        print(safe)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Master Sync Runner — All phases of BrsApi data sync",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--phases", type=int, nargs="+",
        default=[1, 2, 3, 4, 5, 6],
        choices=range(1, 7),
        help="Phases to run (default: all 1-6)",
    )
    parser.add_argument(
        "--symbols", type=int, default=200,
        help="Max symbols per phase (default: 200, 0=all)",
    )
    parser.add_argument(
        "--daily-limit", type=int, default=5000,
        help="BrsApi daily request limit (default: 5000)",
    )
    parser.add_argument(
        "--cron", action="store_true",
        help="Cron mode: skip Phase 2 (detail-heavy), run quick phases only",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be synced without actually fetching",
    )

    args = parser.parse_args()

    # ── Cron mode: skip phases that consume too many requests ──
    if args.cron:
        args.phases = [p for p in args.phases if p not in (2,)]
        _print("⏰ Cron mode: skipping Phase 2 (symbol details)")

    if args.dry_run:
        _print("🔍 DRY RUN — no API calls will be made")
        _print(f"  Phases: {args.phases}")
        _print(f"  Symbols: {args.symbols}")
        _print(f"  Daily limit: {args.daily_limit}")
        return

    # ── Run Master Sync ──
    from core.database import get_session
    from services.sync_master_service import MasterSyncService

    master = MasterSyncService(
        max_symbols_per_phase=args.symbols,
        daily_limit=args.daily_limit,
        skip_502=True,
    )

    _print(f"\n{'='*70}")
    _print("  🚀 MASTER SYNC RUNNER")
    _print(f"  Phases: {args.phases}")
    _print(f"  Symbols: {args.symbols or 'all'}")
    _print(f"  Daily limit: {args.daily_limit}")
    _print(f"{'='*70}\n")

    t0 = time.monotonic()

    async for session in get_session():
        # Rollback any leftover failed transaction
        await session.rollback()

        report = await master.run_all(session, phases=args.phases)

        # Print report
        report.print_summary()
        elapsed = time.monotonic() - t0
        _print(f"\n  ⏱  Wall clock: {elapsed:.1f}s")
        break

    # Cleanup
    await master.close()

    _print("\n  👋 Done!\n")


def _handle_signal() -> None:
    """Handle Ctrl+C gracefully."""
    _print("\n\n⚠️  Received shutdown signal, cleaning up...")
    # Cancel all pending tasks
    for task in asyncio.all_tasks():
        task.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _print("\n⚠️  Interrupted by user")
    except asyncio.CancelledError:
        _print("\n⚠️  Tasks cancelled during shutdown")
    finally:
        _print("  Goodbye!\n")
