#!/usr/bin/env python
"""
Import Codal announcement JSON files into the codal_reports table.

Reads all JSON files from codal_data/ directory and maps each announcement
to a CodalReportModel row.

Mapping:
  l18             -> symbol
  l30             -> company_name
  title           -> summary (the announcement title)
  code            -> report_type
  date_title      -> fiscal_year (fiscal year / period end date)
  date_publish    -> publish_date
  link            -> attachment_url (main report link)
  data_source     =  "codal_json_import"
"""

from __future__ import annotations

# --- auto PYTHONPATH ---
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import asyncio
import hashlib
import json
import re
import sys
import time
from pathlib import Path

# Project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Fix console encoding for Persian characters
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from models.codal import CodalReportModel
from models.instrument import InstrumentModel

DIR_PATH = Path("codal_data")
BATCH_COMMIT = 50  # commit every N files


async def main() -> None:
    from core.database import close_database, get_session, init_database

    start_time = time.monotonic()

    await init_database()

    async for session in get_session():
        # ── 1. Build symbol -> instrument_id mapping ──
        print("Loading instruments mapping ...", flush=True)
        stmt = select(InstrumentModel.id, InstrumentModel.symbol)
        result = await session.execute(stmt)
        symbol_map: dict[str, str] = {}
        for row in result.fetchall():
            sym = (row.symbol or "").strip()
            if sym:
                symbol_map[sym] = row.id

        print(f"Found {len(symbol_map)} instruments in DB", flush=True)

        # ── 2. Count existing codal records ──
        cnt = await session.execute(select(func.count()).select_from(CodalReportModel))
        existing_before = cnt.scalar() or 0
        print(f"Existing codal_reports: {existing_before}", flush=True)

        # ── 3. List JSON files ──
        all_files = sorted(DIR_PATH.glob("*.json"))
        print(f"Found {len(all_files)} JSON files in {DIR_PATH}", flush=True)

        # ── 4. Process each file ──
        stats = {
            "total_files": 0,
            "total_records": 0,
            "imported": 0,
            "skipped_no_instrument": 0,
            "errors": 0,
            "missing_symbols": set(),
            "error_files": [],
        }

        def make_id(symbol: str, date_send: str, time_send: str, code: str) -> str:
            raw = f"{symbol}|{date_send}|{time_send}|{code}"
            h = hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]
            return f"cod_{h}"

        def parse_fiscal_year(date_title: str | None) -> str:
            if date_title and len(date_title) >= 4:
                return date_title[:7]  # "۱۴۰۴/۱۲" or full "۱۴۰۴/۱۲/۲۹"
            return ""

        for file_idx, file_path in enumerate(all_files, 1):
            symbol = file_path.stem.strip()
            file_start = time.monotonic()

            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as exc:
                print(
                    f"  [{file_idx}/{len(all_files)}] ERROR reading {repr(file_path.name)}: {exc}", flush=True
                )
                stats["errors"] += 1
                stats["error_files"].append(file_path.name)
                continue

            announcements = data.get("announcements", []) if isinstance(data, dict) else (
                data if isinstance(data, list) else []
            )
            # If the data is a list, treat each item as a separate announcement
            if isinstance(data, list):
                announcements = data
            elif isinstance(data, dict) and "announcements" not in data:
                # Might be a list under a different key or the data itself
                announcements = [data]

            if not announcements:
                continue

            # Resolve instrument_id
            instrument_id = symbol_map.get(symbol)
            if not instrument_id:
                stats["skipped_no_instrument"] += len(announcements)
                stats["missing_symbols"].add(symbol)
                continue

            records_to_insert = []
            for ann in announcements:
                if not isinstance(ann, dict):
                    continue

                l18 = ann.get("l18") or symbol
                l30 = ann.get("l30") or ""
                title = ann.get("title") or ""
                code = ann.get("code") or ""
                date_title = ann.get("date_title") or None
                date_send = ann.get("date_send") or ""
                time_send = ann.get("time_send") or ""
                date_publish = ann.get("date_publish") or ""
                link = ann.get("link") or ""

                if not code and not title:
                    continue

                record_id = make_id(l18 or symbol, date_send, time_send, code)
                fiscal_year = parse_fiscal_year(date_title)

                # Extract period from title if possible
                period = ""
                if title:
                    period_match = re.search(
                        r"دوره\s*(\d+\s*ماهه)", title
                    )
                    if period_match:
                        period = period_match.group(1)

                records_to_insert.append({
                    "id": record_id,
                    "instrument_id": instrument_id,
                    "symbol": l18 or symbol,
                    "company_name": l30 or "",
                    "isin": "",
                    "report_type": code or "",
                    "fiscal_year": fiscal_year,
                    "period": period,
                    "audit_status": "",
                    "publish_date": date_publish or None,
                    "attachment_url": link or "",
                    "summary": (title or "")[:2000],
                    "data_source": "codal_json_import",
                })

            if not records_to_insert:
                continue

            stats["total_files"] += 1
            stats["total_records"] += len(records_to_insert)

            # Batch insert with on_conflict_do_nothing
            try:
                stmt = pg_insert(CodalReportModel).values(records_to_insert)
                stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
                await session.execute(stmt)
                stats["imported"] += len(records_to_insert)
            except Exception:
                # Fallback: insert one by one
                for rec in records_to_insert:
                    try:
                        stmt = pg_insert(CodalReportModel).values([rec])
                        stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
                        await session.execute(stmt)
                        stats["imported"] += 1
                    except Exception as exc2:
                        stats["errors"] += 1
                        print(f"    Error inserting {rec['id']}: {exc2}", flush=True)

            elapsed = time.monotonic() - file_start
            if file_idx % 10 == 0 or file_idx == len(all_files):
                print(
                    f"  [{file_idx}/{len(all_files)}] "
                    f"file={repr(file_path.name)} "
                    f"records={len(records_to_insert)} "
                    f"total_imported={stats['imported']} "
                    f"({elapsed:.1f}s)",
                    flush=True,
                )

            # Commit periodically
            if stats["total_files"] % BATCH_COMMIT == 0 and stats["total_files"] > 0:
                await session.commit()

        # Final commit
        await session.commit()

        elapsed = time.monotonic() - start_time

    await close_database()

    # ── Summary ──
    print()
    print("=" * 60)
    print("  CODAL JSON IMPORT SUMMARY")
    print("=" * 60)
    print(f"  Files processed:     {stats['total_files']}")
    print(f"  Total records:       {stats['total_records']}")
    print(f"  Imported (new):      {stats['imported']}")
    print(f"  Skipped (no instr):  {stats['skipped_no_instrument']}")
    print(f"  Errors:              {stats['errors']}")
    print(f"  Time:                {elapsed:.1f}s")
    print("=" * 60)

    if stats["missing_symbols"]:
        print(f"\n  Missing instruments ({len(stats['missing_symbols'])} symbols):")
        for sym in sorted(stats["missing_symbols"]):
            print(f"    - {repr(sym)}")

    if stats["error_files"]:
        print(f"\n  Error files ({len(stats['error_files'])}):")
        for f in stats["error_files"][:10]:
            print(f"    - {f}")

    print()


if __name__ == "__main__":
    asyncio.run(main())
