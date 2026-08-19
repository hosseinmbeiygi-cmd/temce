"""Full NAV sync run (mirrors SyncNavAllJob) — per-symbol results + summary.

Usage:  python scripts/_nav_full_run.py 2> scripts/_nav_full_run.log
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brsapi.client import get_client
from brsapi.services.sync_service import BrsApiSyncService
from core.database import get_session

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_nav_full_results.json")


async def main() -> None:
    client = await get_client()
    start = time.time()
    async for session in get_session():
        service = BrsApiSyncService(client=client)
        syms = await service._get_fund_symbols(session)
        print(f"[run] total clean fund symbols: {len(syms)}", flush=True)

        results: dict[str, dict] = {}
        for i, symbol in enumerate(syms):
            if i > 0:
                await asyncio.sleep(11.0)
            try:
                report = await asyncio.wait_for(service.sync_nav(session, symbol), timeout=150)
                results[symbol] = {
                    "success": report.success,
                    "skipped": report.skipped,
                    "items": report.items_count,
                    "error": report.error,
                }
                if report.success and not report.skipped:
                    print(f"[ok] {symbol}", flush=True)
                elif report.skipped:
                    print(f"[skip] {symbol}", flush=True)
                else:
                    print(f"[FAIL] {symbol}: {report.error}", flush=True)
            except Exception as exc:  # noqa: BLE001
                results[symbol] = {"success": False, "error": str(exc)}
                print(f"[EXC] {symbol}: {exc}", flush=True)

            if (i + 1) % 25 == 0:
                elapsed = time.time() - start
                print(f"[progress] {i + 1}/{len(syms)} after {elapsed:.0f}s", flush=True)

        # Persist results for the parent process to read.
        ok = [s for s, r in results.items() if r.get("success") and not r.get("skipped")]
        skipped = [s for s, r in results.items() if r.get("skipped")]
        failed = [s for s, r in results.items() if not r.get("success")]
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump({"results": results, "ok": ok, "skipped": skipped, "failed": failed}, f, ensure_ascii=False, indent=1)

        print(f"\n[summary] total={len(syms)} ok={len(ok)} skipped={len(skipped)} failed={len(failed)} "
              f"duration={time.time() - start:.0f}s", flush=True)
        print(f"[summary] failed_sample={failed[:30]}", flush=True)


asyncio.run(main())
