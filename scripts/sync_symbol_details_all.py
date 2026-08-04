#!/usr/bin/env python
"""
Sync symbol_details for ALL instruments.

This script fetches Symbol.php detail for every symbol in the instruments
table and stores the results in brsapi_symbol_details.

Usage:
    python scripts/sync_symbol_details_all.py [--limit N] [--delay SECONDS] [--dry-run]

Rate limit: ~30 req/min for TSETMC, so default delay is 2.5s between requests.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

# --- auto PYTHONPATH ---
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from brsapi.client import get_client
from brsapi.services.sync_service import BrsApiSyncService
from core.config import settings


# ── Colors ──────────────────────────────────────────────────
class Style:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

def ok(t): return f"{Style.GREEN}{Style.BOLD}{t}{Style.RESET}"
def fail(t): return f"{Style.RED}{Style.BOLD}{t}{Style.RESET}"
def warn(t): return f"{Style.YELLOW}{t}{Style.RESET}"
def header(t): return f"{Style.CYAN}{Style.BOLD}{t}{Style.RESET}"


async def get_all_symbols(session: AsyncSession, limit: int | None = None) -> list[str]:
    """Get all unique symbols from instruments table, ordered alphabetically."""
    query = """
        SELECT DISTINCT symbol
        FROM instruments
        WHERE symbol IS NOT NULL AND symbol != ''
        ORDER BY symbol
    """
    if limit:
        query += f" LIMIT {limit}"
    result = await session.execute(text(query))
    return [row[0] for row in result.fetchall()]


async def get_synced_symbols(session: AsyncSession) -> set[str]:
    """Get symbols that already have details synced."""
    try:
        result = await session.execute(text("""
            SELECT DISTINCT symbol
            FROM brsapi_symbol_details
            WHERE symbol IS NOT NULL AND symbol != ''
        """))
        return {row[0] for row in result.fetchall()}
    except Exception:
        return set()


async def main():
    parser = argparse.ArgumentParser(description="Sync symbol_details for all instruments")
    parser.add_argument("--limit", type=int, default=None, help="Max symbols to sync (default: all)")
    parser.add_argument("--delay", type=float, default=2.5, help="Delay between requests in seconds (default: 2.5)")
    parser.add_argument("--skip-synced", action="store_true", default=True, help="Skip already synced symbols (default: True)")
    parser.add_argument("--no-skip-synced", action="store_false", dest="skip_synced", help="Re-sync all symbols even if already done")
    parser.add_argument("--dry-run", action="store_true", help="Only show what would be synced")
    args = parser.parse_args()

    print(f"\n{header('━' * 60)}")
    print(f"  {header('Sync Symbol Details — All Instruments')}")
    print(f"{header('━' * 60)}")

    # ── Connect to DB ──
    db_url = settings.database_url
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(
        db_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as session:
            # 1. Get all symbols
            symbols = await get_all_symbols(session, args.limit)
            print(f"\n  📊 Total symbols in instruments: {len(symbols)}")

            # 2. Check already synced
            if args.skip_synced:
                synced = await get_synced_symbols(session)
                symbols = [s for s in symbols if s not in synced]
                print(f"  ✅ Already synced: {len(synced)}")
                print(f"  🔄 Remaining to sync: {len(symbols)}")
            else:
                print(f"  🔄 Will re-sync all {len(symbols)} symbols")

            if not symbols:
                print(f"\n  {ok('All symbols already synced!')}")
                return

            if args.dry_run:
                print(f"\n  {warn('DRY RUN — would sync these symbols:')}")
                for s in symbols[:20]:
                    print(f"    - {s}")
                if len(symbols) > 20:
                    print(f"    ... and {len(symbols) - 20} more")
                return

            # 3. Start sync
            print(f"\n  ⏱️  Estimated time: ~{len(symbols) * args.delay / 60:.1f} minutes")
            print(f"  ⚡ Delay between requests: {args.delay}s")
            print(f"\n{header('━' * 60)}")

            client = await get_client()
            sync_svc = BrsApiSyncService(client=client, session=session)

            success_count = 0
            fail_count = 0
            skip_count = 0
            start_time = time.time()

            for idx, symbol in enumerate(symbols, 1):
                elapsed = time.time() - start_time
                eta = (elapsed / idx) * (len(symbols) - idx) if idx > 0 else 0

                try:
                    report = await sync_svc.sync_symbol_detail(session, symbol)
                    if report.success:
                        success_count += 1
                        status = ok("✓")
                        detail = f"{report.items_count} records"
                    elif report.skipped:
                        skip_count += 1
                        status = warn("⏭")
                        detail = "skipped (recent sync exists)"
                    else:
                        fail_count += 1
                        status = fail("✗")
                        detail = report.error or "unknown error"

                    print(f"  [{idx:>4}/{len(symbols)}] {status} {symbol:<12s} {detail:<30s} ETA: {eta:.0f}s")

                except Exception as e:
                    fail_count += 1
                    print(f"  [{idx:>4}/{len(symbols)}] {fail('✗')} {symbol:<12s} {str(e)[:50]}")

                # Commit every 10 symbols
                if idx % 10 == 0:
                    try:
                        await session.commit()
                    except Exception:
                        await session.rollback()

                # Rate limit delay
                if idx < len(symbols):
                    await asyncio.sleep(args.delay)

            # Final commit
            try:
                await session.commit()
            except Exception:
                await session.rollback()

            # Summary
            total_time = time.time() - start_time
            print(f"\n{header('━' * 60)}")
            print(f"  {header('Final Report')}")
            print(f"{header('━' * 60)}")
            print(f"  {ok('✓ Success:')}  {success_count}")
            print(f"  {warn('⏭ Skipped:')} {skip_count}")
            print(f"  {fail('✗ Failed:')}  {fail_count}")
            print(f"  ⏱️  Time:     {total_time:.1f}s ({total_time/60:.1f} min)")
            print(f"{header('━' * 60)}")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
