"""
Run Backlog Sync (budget-aware)
===============================

Runs the BrsApi full-market backfill jobs that fell behind while the API
key was blocked, respecting the daily request budget so the key never gets
itself blocked again.

Steps:
  1. Readiness check - 1 live request to AllSymbols. A 302 redirect to a
     heavy file means the server-side usage counter is still above the plan
     threshold and the run aborts (the key/plan is not ready yet).
  2. Budget plan - the daily budget (default BRSAPI_GLOBAL_DAILY_LIMIT,
     currently 4,000) is split across the requested jobs in priority order;
     candlesticks cost 3 requests/symbol (types 3/2/1), the others 1.
  3. Run - each job processes its symbols through the registry backfill
     logic (missing-first ordering, per-symbol error handling) and the
     global rate limiter enforces the 5-min + daily caps on top.

Usage:
    python scripts/run_backlog_sync.py --dry-run              # readiness + plan only
    python scripts/run_backlog_sync.py                        # real-legal -> symbol-details -> candlesticks
    python scripts/run_backlog_sync.py --jobs real-legal      # single job
    python scripts/run_backlog_sync.py --budget 4000

NOTE: the budget governor (brsapi/budget.py) now ENFORCES the once-per-day
rule — the persisted daily counter (Redis/file, shared across restarts and
replicas) is checked before the plan, so a second run in the same day is
capped to the real remaining budget. The readiness check also aborts if the
server has started redirecting.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from typing import Any

# Ensure the project root is on sys.path for imports
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from brsapi.budget import get_budget_governor  # noqa: E402
from brsapi.client import BrsApiClient  # noqa: E402
from brsapi.config import BrsApiEndpoints  # noqa: E402
from brsapi.config import settings as brsapi_settings
from brsapi.jobs.registry import BrsApiJobRegistry  # noqa: E402
from brsapi.services.sync_service import BrsApiSyncService  # noqa: E402
from core.database import get_session  # noqa: E402
from core.logging import get_logger  # noqa: E402

logger = get_logger(__name__)


def _p(msg: str) -> None:
    """Print helper that avoids UnicodeEncodeError on Windows."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"))


# Request cost per job: (registry job name, requests per symbol, settings cap key)
JOB_PLAN: list[tuple[str, int, str]] = [
    ("brsapi_history_real_legal_all", 1, "history_real_legal_daily_max_symbols"),
    ("brsapi_symbol_details_all", 1, "symbol_detail_daily_max_symbols"),
    ("brsapi_candlesticks_all", 3, "candle_daily_max_symbols"),
]
JOB_ALIASES = {
    "real-legal": "brsapi_history_real_legal_all",
    "history-real-legal": "brsapi_history_real_legal_all",
    "symbol-details": "brsapi_symbol_details_all",
    "symbol-detail": "brsapi_symbol_details_all",
    "candlesticks": "brsapi_candlesticks_all",
    "candlestick": "brsapi_candlesticks_all",
}


async def check_ready(client: BrsApiClient) -> tuple[bool, str]:
    """1 live request to AllSymbols. Returns (ready, detail)."""
    result = await client.fetch(BrsApiEndpoints.ALL_SYMBOLS)
    if result.success:
        return True, f"OK - AllSymbols responded ({result.value.status_code})"
    err = result.error or ""
    if "302" in err:
        return False, (
            "NOT READY - server still redirects to a heavy file (HTTP 302); "
            "the usage counter has not reset yet"
        )
    if "BRSAPI_ENABLED=false" in err:
        return False, "BRSAPI_ENABLED=false - DB-only mode is on"
    return False, f"NOT READY - live request failed: {err}"


async def run_job(
    registry: BrsApiJobRegistry,
    session: Any,
    service: BrsApiSyncService,
    job_name: str,
    max_symbols: int,
) -> Any:
    """Run one backfill job via the registry with an explicit symbol cap."""
    if job_name == "brsapi_history_real_legal_all":
        return await registry._run_history_backfill(
            session, service, kind="real_legal",
            max_symbols=max_symbols, allow_weekend=True,
        )
    if job_name == "brsapi_symbol_details_all":
        return await registry._run_symbol_details_all(
            session, service, max_symbols=max_symbols, allow_weekend=True,
        )
    if job_name == "brsapi_candlesticks_all":
        return await registry._run_candlesticks_all(
            session, service, max_symbols=max_symbols, allow_weekend=True,
        )
    return None


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=str, default="real-legal,symbol-details,candlesticks",
                        help="Comma-separated job list (real-legal, symbol-details, candlesticks)")
    parser.add_argument("--budget", type=int, default=None,
                        help="Max live requests for this run (default: BRSAPI_GLOBAL_DAILY_LIMIT)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Check readiness + print the plan, run nothing")
    args = parser.parse_args(argv)

    if not brsapi_settings.enabled:
        _p("BRSAPI_ENABLED=false - DB-only mode. Set BRSAPI_ENABLED=true to run live syncs.")
        return 1

    budget = args.budget or brsapi_settings.global_daily_limit
    budget = min(budget, brsapi_settings.global_daily_limit)  # never exceed the daily cap

    client = BrsApiClient()
    await client.start()

    # Cap the plan to what the PERSISTED budget (shared across restarts and
    # replicas) still has for today — a second run (or a restarted worker)
    # must not spend the same budget again and re-block the key.
    governor = get_budget_governor()
    gstats = await governor.stats()
    _p(f"Persisted daily usage: {gstats['global']['daily_count']}/"
       f"{gstats['global']['daily_limit']} (backend: {gstats['governor']['backend']})")
    if gstats["block"]["blocked"]:
        _p("Key is in the 302-cooldown (budget governor) — aborting. Run later.")
        await client.stop()
        return 1
    budget = min(budget, int(gstats["global"]["daily_remaining"]))
    if budget <= 0:
        _p("No daily budget left (persisted counter) — run again tomorrow.")
        await client.stop()
        return 1

    _p(f"BrsApi: {brsapi_settings.base_url}")
    _p(f"Daily budget: {budget} requests | enabled: {brsapi_settings.enabled}")
    _p("--- readiness check (1 live request) ---")
    ready, detail = await check_ready(client)
    _p(f"  {detail}")

    if not ready:
        await client.stop()
        _p("Aborted: key not ready. Re-run once the server-side counter resets "
           "(check https://Api.BrsApi.ir/Panel/panel.html).")
        return 1

    # ---- Budget plan -------------------------------------------------
    jobs = []
    for alias in (j.strip() for j in args.jobs.split(",") if j.strip()):
        name = JOB_ALIASES.get(alias, alias)
        if name not in dict(JOB_PLAN):
            _p(f"  [!] Unknown job: {alias} (skip)")
            continue
        jobs.append(name)

    if not jobs:
        _p("No jobs selected.")
        await client.stop()
        return 1

    plan: list[tuple[str, int, int]] = []  # (job, requests, symbols)
    remaining = budget
    for job_name, cost, cap_attr in JOB_PLAN:
        if job_name not in jobs:
            continue
        settings_cap = getattr(brsapi_settings, cap_attr) or 0
        symbol_cap = min(remaining // cost, settings_cap) if settings_cap > 0 else remaining // cost
        symbol_cap = max(symbol_cap, 0)
        reqs = symbol_cap * cost
        plan.append((job_name, reqs, symbol_cap))
        remaining -= reqs

    _p("--- plan ---")
    for job_name, reqs, symbols in plan:
        _p(f"  {job_name}: {symbols} symbols -> ~{reqs} requests")
    _p(f"  total ~{budget - remaining} requests (budget {budget})")
    _p("  NOTE: run at most once per day (in-process limiter resets each run).")

    if args.dry_run:
        await client.stop()
        _p("--- DRY RUN - nothing executed ---")
        return 0

    # ---- Run ---------------------------------------------------------
    registry = BrsApiJobRegistry()
    registry._client = client
    async for session in get_session():
        service = BrsApiSyncService(client=client)
        for job_name, reqs, symbols in plan:
            if symbols <= 0:
                _p(f"\n  [SKIP] {job_name}: no budget left")
                continue
            _p(f"\n{'='*60}\n  [RUN] {job_name} ({symbols} symbols, ~{reqs} req)\n{'='*60}")
            t0 = time.monotonic()
            report = await run_job(registry, session, service, job_name, symbols)
            elapsed = (time.monotonic() - t0) / 60
            if report is None:
                _p(f"  [FAIL] {job_name}: no report (aborted?)")
                continue
            status = "OK" if report.success else "FAIL"
            _p(f"  [{status}] {job_name}: {report.items_count} items in {elapsed:.1f}min")
            if report.error:
                _p(f"  [ERROR] {report.error[:300]}")
        break

    gstats = await governor.stats()
    _p(f"\n--- budget governor: {gstats['global']['daily_count']}/"
       f"{gstats['global']['daily_limit']} used today (backend: {gstats['governor']['backend']}) ---")

    await client.stop()
    _p("[DONE] Backlog sync finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
