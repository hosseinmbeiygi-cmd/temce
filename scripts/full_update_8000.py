#!/usr/bin/env python
"""
Full Update with 8000 request cap.

Updates all tables respecting BrsApiBudgetGovernor daily limit.
Prioritizes real-time tables first, then backfills in chunks.

Usage:
    python scripts/full_update_8000.py              # 8000 limit
    python scripts/full_update_8000.py --limit 3000 # custom limit
    python scripts/full_update_8000.py --dry-run    # plan only
"""

import argparse
import asyncio
import time
from datetime import datetime

from brsapi.budget import get_budget_governor
from brsapi.config import get_brsapi_settings
from brsapi.jobs.registry import BRsAPI_SYNC_JOBS, BrsApiJobRegistry

# Priority order: real-time first, then daily backfills
PRIORITY_ORDER = [
    # Tier 1: Real-time critical (1 req each) ~10 reqs
    "brsapi_all_symbols",
    "brsapi_index",
    "brsapi_index_farabours",
    "brsapi_gold_currency_pro",  # Pro gold/currency
    "brsapi_gold_currency",  # Gold/currency
    "brsapi_commodities",
    "brsapi_crypto",
    "brsapi_ime_funds",
    "brsapi_ime_futures",
    "brsapi_ime_options",
    "brsapi_ime_certificates",
    "brsapi_codal",
    # Tier 2: Daily backfills (chunked, high cost)
    "brsapi_candlesticks_all",
    "brsapi_shareholders_all",
    "brsapi_history_price_all",
    "brsapi_history_real_legal_all",
    "brsapi_symbol_details_all",
    "brsapi_ime_physical",
]

# Estimated cost per job (for planning)
ESTIMATED_COST = {
    "brsapi_all_symbols": 1,
    "brsapi_index": 1,
    "brsapi_index_farabours": 1,
    "brsapi_gold_currency_pro": 3,  # section=gold+currency+crypto
    "brsapi_gold_currency": 2,
    "brsapi_commodities": 1,
    "brsapi_crypto": 1,
    "brsapi_ime_funds": 1,
    "brsapi_ime_futures": 1,
    "brsapi_ime_options": 1,
    "brsapi_ime_certificates": 1,
    "brsapi_codal": 1,
    "brsapi_candlesticks_all": 1500,  # 500 symbols *3 types, chunked
    "brsapi_shareholders_all": 500,  # 500 symbols
    "brsapi_history_price_all": 500,
    "brsapi_history_real_legal_all": 500,
    "brsapi_symbol_details_all": 500,
    "brsapi_ime_physical": 1,
}

# Chunk sizes that fit within 8000 budget
CHUNK_SIZES = {
    "brsapi_candlesticks_all": 400,  # 400*3=1200 reqs
    "brsapi_shareholders_all": 400,  # 400 reqs
    "brsapi_history_price_all": 400,  # 400 reqs
    "brsapi_history_real_legal_all": 400,
    "brsapi_symbol_details_all": 400,
}


async def run_full_update(limit: int = 8000, dry_run: bool = False):
    settings = get_brsapi_settings()
    governor = get_budget_governor()
    await governor.initialize()
    stats = await governor.stats()

    used_before = stats["global"]["daily_count"]
    remaining_before = stats["global"]["daily_remaining"]

    print("=" * 70)
    print("  Full Update - 8000 Request Cap")
    print("=" * 70)
    print(
        f"  Budget before: {used_before}/{stats['global']['daily_limit']} used ({stats['global']['daily_used_pct']}%)"
    )
    print(f"  Remaining: {remaining_before}")
    print(f"  Request cap: {limit}")
    print(f"  Time: {datetime.now().isoformat()}")
    print(f"  Backend: {stats['governor']['backend']}")
    if stats["block"]["blocked"]:
        print(f"  ⚠️ BLOCKED until {stats['block']['blocked_until']}")
        return
    print("=" * 70)

    # Build plan
    total_estimated = sum(ESTIMATED_COST.get(j, 1) for j in PRIORITY_ORDER)
    print(f"\n  PLAN (total est. {total_estimated} reqs):")
    cumulative = 0
    plan = []
    for job in PRIORITY_ORDER:
        cost = ESTIMATED_COST.get(job, 1)
        cumulative += cost
        status = "[OK]" if cumulative <= limit else "[SKIP]"
        print(f"    {status} {job:35} ~{cost:4} reqs (cum: {cumulative:4})")
        if cumulative <= limit:
            plan.append(job)

    if dry_run:
        print(f"\n  DRY RUN - would execute {len(plan)} jobs, ~{cumulative} reqs")
        print(f"  Remaining after: {remaining_before - sum(ESTIMATED_COST.get(j, 1) for j in plan)}")
        return

    # Execute plan
    print(f"\n  EXECUTING {len(plan)} jobs...")
    print("-" * 70)

    registry = BrsApiJobRegistry()
    registry.register_many(BRsAPI_SYNC_JOBS)

    total_items = 0
    total_failed = 0
    executed = 0
    start = time.monotonic()

    for job_name in plan:
        # Budget check before each job
        current = await governor.stats()
        remaining = current["global"]["daily_remaining"]
        used = current["global"]["daily_count"]

        estimated = ESTIMATED_COST.get(job_name, 1)
        if remaining < estimated:
            print(f"\n  ⚠️ Budget exhausted before {job_name}: {remaining} remaining < {estimated} estimated")
            print(f"     Stopping to protect key (used {used}/{current['global']['daily_limit']})")
            break

        # Check 8000 cap specifically
        requests_used_this_run = used - used_before
        if requests_used_this_run >= limit:
            print(f"\n  🛑 8000 cap reached: {requests_used_this_run}/{limit} used this run")
            break
        if requests_used_this_run + estimated > limit:
            print(f"\n  ⏭️ Skipping {job_name}: would exceed 8000 cap ({requests_used_this_run}+{estimated} > {limit})")
            continue

        print(f"\n  ▶ {job_name} (est. {estimated} reqs, remaining {remaining}, run {requests_used_this_run}/{limit})")

        try:
            # Special handling for chunked jobs
            kwargs = {}
            if job_name in CHUNK_SIZES:
                kwargs["max_symbols"] = CHUNK_SIZES[job_name]
                print(f"    chunk size: {kwargs['max_symbols']}")

            # Run with force=True to bypass market-hours gate (admin update)
            if kwargs:
                # Call internal method with chunk limit
                if job_name == "brsapi_candlesticks_all":
                    result = await registry._run_candlesticks_all(
                        await get_session_for_registry(registry),
                        await get_service(registry),
                        max_symbols=kwargs["max_symbols"],
                    )
                elif job_name == "brsapi_shareholders_all":
                    result = await registry._run_shareholders_all(
                        await get_session_for_registry(registry),
                        await get_service(registry),
                        max_symbols=kwargs["max_symbols"],
                    )
                else:
                    result = await registry.run_job(job_name, force=True)
            else:
                result = await registry.run_job(job_name, force=True)

            if result is None:
                print("    ⏭️ Skipped (market hours / no data)")
                continue

            executed += 1
            total_items += result.items_count if result.items_count else 0
            status_icon = "✅" if result.success else "❌"
            print(
                f"    {status_icon} {result.items_count} items in {result.duration_ms:.0f}ms"
                + (f" error: {result.error}" if result.error else "")
            )

            if not result.success and result.error:
                total_failed += 1

            # Small delay between jobs to avoid hammering
            await asyncio.sleep(1)

        except Exception as e:
            print(f"    ❌ Exception: {e}")
            total_failed += 1
            import traceback

            traceback.print_exc()

    elapsed = time.monotonic() - start
    final = await governor.stats()
    used_after = final["global"]["daily_count"]
    run_used = used_after - used_before

    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  Jobs executed: {executed}/{len(plan)}")
    print(f"  Total items: {total_items}")
    print(f"  Failed jobs: {total_failed}")
    print(f"  Requests this run: {run_used}/{limit} ({run_used / limit * 100:.1f}%)")
    print(f"  Budget: {used_before} -> {used_after} / {final['global']['daily_limit']}")
    print(f"  Remaining: {final['global']['daily_remaining']}")
    print(f"  Time: {elapsed:.1f}s ({elapsed / 60:.1f} min)")
    print(f"  Blocked: {final['block']['blocked']}")
    print("=" * 70)

    if run_used > limit:
        print(f"  ⚠️ WARNING: Exceeded 8000 cap by {run_used - limit} requests!")
    else:
        print(f"  ✅ Within 8000 cap: {limit - run_used} requests spare")


async def get_session_for_registry(registry):
    from core.database import get_session

    async for s in get_session():
        return s


async def get_service(registry):
    from brsapi.client import get_client
    from brsapi.services.sync_service import BrsApiSyncService

    client = await get_client()
    return BrsApiSyncService(client=client)


def main():
    parser = argparse.ArgumentParser(description="Full update with 8000 cap")
    parser.add_argument("--limit", type=int, default=8000, help="Max requests this run (default 8000)")
    parser.add_argument("--dry-run", action="store_true", help="Plan only, no execution")
    args = parser.parse_args()
    asyncio.run(run_full_update(limit=args.limit, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
