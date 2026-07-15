"""
Integration test: fetch TSETMC AllSymbols from BrsApi and verify DB storage.

Usage:
    BRSAPI_API_KEY=FreeSV0E1LSgB9RDjuf0QorSLViX8pPG python -m brsapi.tests.test_tsetmc_symbols_integration

Requires:
    - PostgreSQL running (DATABASE_URL in .env)
    - BRSAPI_API_KEY env var or pass via --key
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from core.database import close_database, get_session, init_database


async def main(api_key: str) -> int:
    # ── 1. Set API key ────────────────────────────
    os.environ.setdefault("BRSAPI_API_KEY", api_key)

    from brsapi.services.sync_service import BrsApiSyncService

    # ── 2. Init database ──────────────────────────
    print("Initializing database connection...")
    await init_database()
    print("  [OK] Database connected")

    # ── 3. Create sync service ────────────────────
    service = BrsApiSyncService()

    # ── 4. Health check ───────────────────────────
    print("\nChecking BrsApi connectivity...")
    health = await service.health()
    print(f"  Client ready: {health['ready']}")
    print(f"  API reachable: {health['reachable']}")
    if not health["reachable"]:
        print(f"  ERROR: {health['error']}")
        await close_database()
        return 1
    print(f"  Rate limit tokens: {health['rate_limit_buckets']}")
    print("  [OK] BrsApi reachable")

    # ── 5. Sync all symbols (type=1 = stocks) ────
    print("\nFetching TSETMC symbols (type=1 - stocks & ETFs)...")
    t0 = time.monotonic()

    async with get_session() as session:
        report = await service.sync_all_symbols(session, symbol_type="1")

    elapsed = time.monotonic() - t0
    print(f"  Endpoint: {report.endpoint}")
    print(f"  Success: {report.success}")
    print(f"  Records stored: {report.items_count}")
    print(f"  Duration: {report.duration_ms:.0f} ms (wall: {elapsed:.1f}s)")
    print(f"  Skipped (dedup): {report.skipped}")

    if not report.success:
        print(f"  ERROR: {report.error}")
        await close_database()
        return 1

    # ── 6. Verify in database ─────────────────────
    print("\nVerifying data in PostgreSQL...")
    async with get_session() as session:
        from sqlalchemy import func as sa_func
        from sqlalchemy import select

        from brsapi.models import SymbolSnapshotModel

        # Total count
        cnt_result = await session.execute(
            select(sa_func.count()).select_from(SymbolSnapshotModel)
        )
        total = cnt_result.scalar() or 0
        print(f"  Total rows in brsapi_symbol_snapshots: {total}")

        # Unique symbols
        distinct_result = await session.execute(
            select(sa_func.count(SymbolSnapshotModel.symbol.distinct()))
        )
        distinct = distinct_result.scalar() or 0
        print(f"  Unique symbols: {distinct}")

        # Sample records
        sample_result = await session.execute(
            select(SymbolSnapshotModel)
            .order_by(SymbolSnapshotModel.trade_value.desc().nullslast())
            .limit(5)
        )
        sample = sample_result.scalars().all()
        print("\n  Top 5 symbols by trade value:")
        for row in sample:
            print(
                f"    - {row.symbol:10s} | "
                f"last={row.price_last:>8.0f} | "
                f"change={row.price_last_change_pct:>+6.2f}% | "
                f"volume={row.trade_volume:>12,} | "
                f"value={row.trade_value:>15,.0f}"
            )

        # Check sync log
        from brsapi.repositories.base import SyncLogRepository

        log_repo = SyncLogRepository(session)
        last = await log_repo.last_sync(report.endpoint)
        if last:
            print(
                f"\n  Last sync log: status={last.status}, "
                f"items={last.items_count}, "
                f"duration={last.duration_ms:.0f}ms"
            )

    # ── 7. Summary ────────────────────────────────
    print(f"\n{'='*50}")
    print("  [PASS] INTEGRATION TEST PASSED")
    print(f"  Fetched {report.items_count} records for {distinct} unique symbols")
    print(f"  Stored in brsapi_symbol_snapshots ({total} total rows)")
    print(f"{'='*50}")

    await close_database()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Integration test: fetch TSETMC symbols via BrsApi"
    )
    parser.add_argument(
        "--key",
        default=os.environ.get("BRSAPI_API_KEY", "FreeSV0E1LSgB9RDjuf0QorSLViX8pPG"),
        help="BrsApi.ir API key (default: free demo key)",
    )
    args = parser.parse_args()

    exit_code = asyncio.run(main(args.key))
    sys.exit(exit_code)
