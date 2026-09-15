#!/usr/bin/env python3
"""
Update ALL BrsApi tables within a hard 10,000 daily request budget.

Respects the persistent budget governor (file/Redis, shared across restarts),
so a second run in the same day is capped to the REAL remaining budget and
never re-blocks the key.

Priority: real-time tables first (cheap, 1-3 req each), then chunked
per-symbol backfills (candlesticks 3/sym, others 1/sym), ordered so the
most business-critical history fills first. Each backfill job is
missing-first, so re-running tomorrow seamlessly resumes with the symbols
that still lack data.

Stops the moment the daily budget is gone — no hammering, no over-quota.

Usage:
    python scripts/update_all_tables_budgeted.py --dry-run
    python scripts/update_all_tables_budgeted.py
    python scripts/update_all_tables_budgeted.py --budget 5000
"""

import argparse
import asyncio
import os
import sys

# Ensure project root on sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Fix network/proxy BEFORE any HTTP
from core.fix_network import fix_network

fix_network()

from brsapi.budget import get_budget_governor
from brsapi.client import BrsApiClient
from brsapi.config import BrsApiEndpoints
from brsapi.config import settings as brsapi_settings
from brsapi.jobs.registry import BrsApiJobRegistry
from brsapi.services.sync_service import BrsApiSyncService
from core.database import get_session
from core.logging import get_logger

logger = get_logger(__name__)


def _p(msg: str) -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"))


# Realtime / bulk jobs — fixed cost, no per-symbol loop.
REALTIME_JOBS: list[tuple[str, int]] = [
    ("brsapi_all_symbols", 1),
    ("brsapi_index", 1),
    ("brsapi_index_farabours", 1),
    ("brsapi_gold_currency_pro", 3),
    ("brsapi_gold_currency", 2),
    ("brsapi_commodities", 1),
    ("brsapi_crypto", 1),
    ("brsapi_ime_funds", 1),
    ("brsapi_ime_futures", 1),
    ("brsapi_ime_options", 1),
    ("brsapi_ime_certificates", 1),
    ("brsapi_codal", 2),
    ("brsapi_ime_physical", 1),
]

# Per-symbol backfill jobs — (job, cost_per_symbol, settings_cap_attr).
# Ordered: candlesticks + daily history first (price series), then real/legal,
# shareholders, symbol-details.
BACKFILL_JOBS: list[tuple[str, int, str]] = [
    ("brsapi_candlesticks_all", 3, "candle_daily_max_symbols"),
    ("brsapi_history_price_all", 1, "history_price_daily_max_symbols"),
    ("brsapi_history_real_legal_all", 1, "history_real_legal_daily_max_symbols"),
    ("brsapi_shareholders_all", 1, "shareholder_daily_max_symbols"),
    ("brsapi_symbol_details_all", 1, "symbol_detail_daily_max_symbols"),
]


async def run_backfill(registry, session, service, job_name, max_symbols):
    """Run one chunked per-symbol backfill with an explicit symbol cap."""
    if job_name == "brsapi_candlesticks_all":
        return await registry._run_candlesticks_all(
            session, service, max_symbols=max_symbols, allow_weekend=True
        )
    if job_name == "brsapi_shareholders_all":
        return await registry._run_shareholders_all(
            session, service, max_symbols=max_symbols, allow_weekend=True
        )
    if job_name == "brsapi_history_price_all":
        return await registry._run_history_price_all(
            session, service, max_symbols=max_symbols, allow_weekend=True
        )
    if job_name == "brsapi_history_real_legal_all":
        return await registry._run_history_real_legal_all(
            session, service, max_symbols=max_symbols, allow_weekend=True
        )
    if job_name == "brsapi_symbol_details_all":
        return await registry._run_symbol_details_all(
            session, service, max_symbols=max_symbols, allow_weekend=True
        )
    return None


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--budget", type=int, default=None,
        help="Max requests this run (default: governor's remaining budget)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Plan only, no execution")
    args = parser.parse_args()

    if not brsapi_settings.enabled:
        _p("BRSAPI_ENABLED=false - DB-only mode. Set BRSAPI_ENABLED=true to run live syncs.")
        return 1

    client = BrsApiClient()
    await client.start()

    governor = get_budget_governor()
    gstats = await governor.stats()
    _p(f"Persisted daily usage: {gstats['global']['daily_count']}/"
       f"{gstats['global']['daily_limit']} (backend: {gstats['governor']['backend']})")
    if gstats["block"]["blocked"]:
        _p("Key is in 302-cooldown — aborting. Run later.")
        await client.stop()
        return 1

    budget = args.budget or gstats["global"]["daily_remaining"]
    budget = min(budget, gstats["global"]["daily_remaining"])
    if budget <= 0:
        _p("No daily budget left (persisted counter) — run again tomorrow.")
        await client.stop()
        return 1

    # Readiness: 1 live request. 302 = server still over quota.
    result = await client.fetch(BrsApiEndpoints.ALL_SYMBOLS)
    if not result.success:
        err = result.error or ""
        if "302" in err:
            _p("NOT READY - server redirects (302), usage counter not reset. Abort.")
        else:
            _p(f"NOT READY - live request failed: {err}")
        await client.stop()
        return 1
    _p("Readiness OK (AllSymbols 200)")

    # ── Plan ──
    plan: list[tuple[str, int, int]] = []  # (job, cost_per, symbols) symbols=0 => realtime
    remaining = budget
    for job, cost in REALTIME_JOBS:
        if remaining >= cost:
            plan.append((job, cost, 0))
            remaining -= cost
    for job, cost, cap_attr in BACKFILL_JOBS:
        settings_cap = getattr(brsapi_settings, cap_attr) or 0
        sym_cap = (
            min(remaining // cost, settings_cap)
            if settings_cap > 0
            else remaining // cost
        )
        sym_cap = max(sym_cap, 0)
        if sym_cap > 0:
            plan.append((job, cost, sym_cap))
            remaining -= sym_cap * cost

    rt = sum(1 for _, _, s in plan if s == 0)
    bf = sum(1 for _, _, s in plan if s > 0)
    _p(f"Plan: {rt} realtime + {bf} backfill jobs, ~{budget - remaining} reqs "
       f"(budget {budget})")

    if args.dry_run:
        for job, cost, sym in plan:
            if sym == 0:
                _p(f"  {job}: realtime (~{cost} req)")
            else:
                _p(f"  {job}: {sym} symbols ~{sym * cost} req")
        await client.stop()
        return 0

    # ── Execute ──
    registry = BrsApiJobRegistry()
    registry._client = client

    async for session in get_session():
        service = BrsApiSyncService(client=client)
        for job, cost, sym in plan:
            # Re-check the live budget before each job.
            cur = await governor.stats()
            if cur["global"]["daily_remaining"] < cost:
                _p(f"\n[STOP] Budget exhausted before {job} "
                   f"({cur['global']['daily_remaining']} left) — resume tomorrow.")
                break
            if sym == 0:
                _p(f"\n{'='*60}\n[RUN] {job} (realtime)\n{'='*60}")
                try:
                    r = await registry.run_job(job, force=True)
                    if r is None:
                        _p(f"  [SKIP] {job}: no-op (market hours / no data)")
                        continue
                    _p(f"  [{'OK' if r.success else 'FAIL'}] {job}: "
                       f"{r.items_count} items"
                       + (f" error: {r.error}" if r.error else ""))
                except Exception as e:  # noqa: BLE001
                    _p(f"  [EXC] {job}: {e}")
            else:
                _p(f"\n{'='*60}\n[RUN] {job} ({sym} symbols)\n{'='*60}")
                try:
                    r = await run_backfill(registry, session, service, job, sym)
                    if r is None:
                        _p(f"  [SKIP] {job}: no-op")
                        continue
                    _p(f"  [{'OK' if r.success else 'FAIL'}] {job}: "
                       f"{r.items_count} items"
                       + (f" error: {r.error}" if r.error else ""))
                except Exception as e:  # noqa: BLE001
                    _p(f"  [EXC] {job}: {e}")
        break

    gstats = await governor.stats()
    _p(f"\n--- budget governor: {gstats['global']['daily_count']}/"
       f"{gstats['global']['daily_limit']} used today "
       f"(backend: {gstats['governor']['backend']}) ---")
    await client.stop()
    _p("[DONE] Update pass finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
