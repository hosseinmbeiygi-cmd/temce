"""Analyze the running NAV full-run: categorize ok/skip/fail and version-2/3 patterns.

Reads scripts/_nav_full_run.log (incremental) and queries DB for symbol metadata.
"""
import asyncio
import os
import re
import sys

sys.path.insert(0, ".")

from sqlalchemy import func, select

from brsapi.models import SymbolSnapshotModel
from core.database import get_session

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_nav_full_run.log")
V2_RE = re.compile(r"^(.+?)(\d+)$")  # symbol ending in digits (e.g. ابتکار2, آتیه ملت4)


def read_log() -> dict[str, list[str]]:
    out = {"ok": [], "skip": [], "fail": [], "exc": []}
    if not os.path.exists(LOG):
        return out
    with open(LOG, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            for key, tag in (("ok", "[ok]"), ("skip", "[skip]"), ("fail", "[FAIL]"), ("exc", "[EXC]")):
                if line.startswith(tag):
                    sym = line[len(tag):].split(":")[0].strip()
                    out[key].append(sym)
                    break
    return out


async def main() -> None:
    run = read_log()
    print(f"log so far: ok={len(run['ok'])} skip={len(run['skip'])} fail={len(run['fail'])} exc={len(run['exc'])}")

    all_seen = run["ok"] + run["skip"] + run["fail"] + run["exc"]
    v2 = [s for s in all_seen if V2_RE.match(s)]
    base = [s for s in all_seen if not V2_RE.match(s)]
    print(f"seen={len(all_seen)}  versioned(ending in digit)={len(v2)}  base={len(base)}")
    print(f"  versioned ok:   {[s for s in v2 if s in run['ok']]}")
    print(f"  versioned skip: {[s for s in v2 if s in run['skip']]}")
    print(f"  versioned fail: {[s for s in v2 if s in run['fail']]}")
    print(f"  base fail:      {[s for s in base if s in run['fail'] or s in run['exc']]}")

    # How many insurance-sector symbols leak into the fund list?
    async for session in get_session():
        r = await session.execute(
            select(SymbolSnapshotModel.sector, func.count(func.distinct(SymbolSnapshotModel.symbol)))
            .where(
                (SymbolSnapshotModel.sector.ilike("%صندوق%"))
                | (func.lower(SymbolSnapshotModel.sector).like("%fund%"))
                | (func.lower(SymbolSnapshotModel.sector).like("%etf%"))
            )
            .group_by(SymbolSnapshotModel.sector)
        )
        print("\n=== sectors matching the current fund filter ===")
        for sec, cnt in r.fetchall():
            print(f"  {cnt:4d}  {sec}")

        # Distinct sectors that contain the word صندوق but are NOT fund sector
        r2 = await session.execute(
            select(SymbolSnapshotModel.sector, func.count(func.distinct(SymbolSnapshotModel.symbol)))
            .where(SymbolSnapshotModel.sector.ilike("%صندوق%"))
            .group_by(SymbolSnapshotModel.sector)
        )
        print("\n=== all sectors containing 'صندوق' ===")
        for sec, cnt in r2.fetchall():
            mark = "  <-- NOT an ETF (insurance/pension)" if "بیمه" in str(sec) else ""
            print(f"  {cnt:4d}  {sec}{mark}")


asyncio.run(main())
