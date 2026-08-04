"""
Import Shareholders from CSV
=============================

Reads archive/shareholder20240821.csv and imports its 944K+ rows
into the `brsapi_shareholder_records` table, then reports any
anomalies or suspicious patterns found in the data.

Data source: TSE shareholder records (Sena / سنا)
Columns (10):
  Shareholder ID, Shareholder name, Stock ID (ISIN),
  Date (YYYYMMDD), Number of shares, Perofshares (%),
  Change (1=inc, 2=dec, 3=?, 0=?), Changeamount,
  shareHolderShareID, Symbol

Usage:
    python scripts/import_shareholders.py
"""

from __future__ import annotations

import csv
import os
import sys
import time
from collections import Counter
from typing import Any

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from core.logging import setup_logging

setup_logging()

CSV_PATH = os.path.join(_project_root, "archive", "shareholder20240821.csv")
BATCH_SIZE = 3000  # Keep under asyncpg's 32,767-param limit (3000 x 8 = 24,000)


def _p(msg: str) -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        safe = msg.encode("ascii", errors="replace").decode("ascii")
        print(safe)


def _clean_row(raw: dict[str, str]) -> dict[str, Any]:
    """Convert a CSV row dict into clean typed values."""
    return {
        "shareholder_id": int(raw.get("Shareholder ID", "0") or "0"),
        "shareholder_name": (raw.get("Shareholder name", "") or "").strip(),
        "stock_id": (raw.get("Stock ID", "") or "").strip(),
        "date_str": (raw.get("Date", "") or "").strip(),
        "shares": int(float(raw.get("Number of shares", "0") or "0")),
        "percent": float(raw.get("Perofshares", "0") or "0"),
        "change_type": int(raw.get("Change", "0") or "0"),
        "change_amount": int(float(raw.get("Changeamount", "0") or "0")),
        "holder_share_id": int(raw.get("shareHolderShareID", "0") or "0"),
        "symbol": (raw.get("Symbol", "") or "").strip(),
    }


def _format_date(date_str: str) -> str | None:
    """Convert YYYYMMDD to YYYY-MM-DD.  Return None if invalid."""
    if len(date_str) == 8 and date_str.isdigit():
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    return None


async def run() -> None:
    from sqlalchemy import text

    from core.database import get_session

    t0 = time.monotonic()

    # ──────────────────────────────────────────────────────────
    # Phase 1: Scan & validate
    # ──────────────────────────────────────────────────────────
    _p("=" * 65)
    _p("📂 SHAREHOLDER CSV IMPORT — Phase 1: Scanning")
    _p("=" * 65)

    if not os.path.exists(CSV_PATH):
        _p(f"❌ CSV not found: {CSV_PATH}")
        return

    file_size = os.path.getsize(CSV_PATH)
    _p(f"File: {CSV_PATH}")
    _p(f"Size: {file_size / 1e6:.1f} MB")

    # First pass: validate structure and gather stats
    total_rows = 0
    invalid_rows = 0
    change_types: Counter[str] = Counter()
    symbols: set[str] = set()
    shareholders: set[str] = set()
    date_min = "99999999"
    date_max = "00000000"
    suspicious: list[str] = []

    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [fn.replace("\ufeff", "") for fn in reader.fieldnames or []]
        cols = reader.fieldnames
        _p(f"Columns ({len(cols)}): {cols}")

        for raw in reader:
            total_rows += 1
            try:
                row = _clean_row(raw)
            except (ValueError, TypeError):
                invalid_rows += 1
                continue

            change_types[str(row["change_type"])] += 1
            symbols.add(row["symbol"])
            shareholders.add(row["shareholder_name"])
            if row["date_str"]:
                if row["date_str"] < date_min:
                    date_min = row["date_str"]
                if row["date_str"] > date_max:
                    date_max = row["date_str"]

            # ---- Suspicious checks (sampled: first 200K rows) ----
            if total_rows <= 200000:
                if row["percent"] > 80:
                    suspicious.append(
                        f"[🔴 OWNERSHIP] {row['symbol']}: {row['shareholder_name'][:30]} "
                        f"owns {row['percent']:.1f}% ({row['shares']:,} shares)"
                    )
                if row["change_type"] == 3:
                    if sum(1 for s in suspicious if "CHANGE_TYPE_3" in s) < 5:
                        suspicious.append(
                            f"[🟡 CHANGE_TYPE_3] {row['symbol']}: {row['shareholder_name'][:25]} "
                            f"shares={row['shares']:,} pct={row['percent']:.2f}%"
                        )
                if abs(row["change_amount"]) > 1_000_000_000_000:
                    suspicious.append(
                        f"[🟠 LARGE_CHANGE] {row['symbol']}: {row['shareholder_name'][:25]} "
                        f"change_amt={row['change_amount']:,}"
                    )
                if row["symbol"] and any(ch in row["symbol"] for ch in "!@#$%^&*()_+=[]{}|;:'\",.<>?/~`"):
                    suspicious.append(
                        f"[🔴 STRANGE_SYMBOL] '{row['symbol']}'"
                    )

    suspicious = list(dict.fromkeys(suspicious))

    _p("\n📊 Scan complete:")
    _p(f"  Total rows:        {total_rows:,}")
    _p(f"  Invalid rows:      {invalid_rows:,}")
    _p(f"  Unique symbols:    {len(symbols):,}")
    _p(f"  Unique holders:    {len(shareholders):,}")
    _p(f"  Date range:        {date_min} → {date_max}")
    _p(f"  Change types:      {dict(change_types)}")

    # ──────────────────────────────────────────────────────────
    # Phase 1b: Ensure UNIQUE constraint for idempotent import
    # ──────────────────────────────────────────────────────────
    _p("\n" + "=" * 65)
    _p("🔒 PHASE 1b: Ensuring UNIQUE constraint")
    _p("=" * 65)

    async for session in get_session():
        await _ensure_constraint(session)
        break

    # ──────────────────────────────────────────────────────────
    # Phase 2: Import
    # ──────────────────────────────────────────────────────────
    _p("\n" + "=" * 65)
    _p("📥 PHASE 2: Importing to brsapi_shareholder_records")
    _p("=" * 65)

    async for session in get_session():
        # Append/upsert based on (symbol, shareholder_name, date)

        imported = 0
        skipped = 0
        errors = 0
        batch: list[dict[str, Any]] = []

        with open(CSV_PATH, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            reader.fieldnames = [fn.replace("\ufeff", "") for fn in reader.fieldnames or []]

            for raw in reader:
                try:
                    row = _clean_row(raw)
                except (ValueError, TypeError):
                    errors += 1
                    continue

                if not row["symbol"] or not row["shareholder_name"]:
                    skipped += 1
                    continue

                batch.append(row)

                if len(batch) >= BATCH_SIZE:
                    await _flush_batch(session, batch)
                    imported += len(batch)
                    batch = []
                    _p(f"  Imported {imported:,} / {total_rows:,} ...")

            # Flush remaining
            if batch:
                await _flush_batch(session, batch)
                imported += len(batch)

        await session.commit()
        elapsed = time.monotonic() - t0

        _p("\n✅ Import complete!")
        _p(f"  Imported:  {imported:,}")
        _p(f"  Skipped:   {skipped:,}")
        _p(f"  Errors:    {errors:,}")
        _p(f"  Time:      {elapsed:.1f}s")

        # ──────────────────────────────────────────────────────────
        # Phase 3: Post-import analysis
        # ──────────────────────────────────────────────────────────
        _p("\n" + "=" * 65)
        _p("🔍 PHASE 3: Post-import analysis")
        _p("=" * 65)

        # Check current count
        r = await session.execute(text("SELECT COUNT(*) FROM brsapi_shareholder_records"))
        total_now = r.scalar()
        _p(f"Records in table: {total_now:,}")

        # Check for duplicate (symbol, shareholder, date) combos
        r = await session.execute(text("""
            SELECT COUNT(*) FROM (
                SELECT symbol, shareholder_name, date
                FROM brsapi_shareholder_records
                GROUP BY symbol, shareholder_name, date
                HAVING COUNT(*) > 1
            ) dup
        """))
        dup_count = r.scalar() or 0
        _p(f"Duplicate (symbol, holder, date): {dup_count:,}")

        # Top holders by max percent
        r = await session.execute(text("""
            SELECT symbol, shareholder_name, MAX(percent) as max_pct,
                   MAX(volume) as max_vol
            FROM brsapi_shareholder_records
            GROUP BY symbol, shareholder_name
            ORDER BY max_pct DESC
            LIMIT 10
        """))
        _p("\n🏆 Top 10 single-holder ownerships:")
        for row in r.fetchall():
            _p(f"  {row[0]:>8s}  {str(row[1])[:35]:35s}  {float(row[2]):>6.2f}%  {row[3]:>15,}")

        # Top holders by max volume
        r = await session.execute(text("""
            SELECT symbol, shareholder_name, MAX(volume) as max_vol, MAX(percent) as pct
            FROM brsapi_shareholder_records
            GROUP BY symbol, shareholder_name
            ORDER BY max_vol DESC
            LIMIT 10
        """))
        _p("\n🏆 Top 10 largest positions (by volume):")
        for row in r.fetchall():
            _p(f"  {row[0]:>8s}  {str(row[1])[:35]:35s}  {row[3]:>6.2f}%  {row[2]:>18,}")

    # ──────────────────────────────────────────────────────────
    # Phase 4: Suspicious report
    # ──────────────────────────────────────────────────────────
    _p("\n" + "=" * 65)
    _p("🚨 SUSPICIOUS FINDINGS REPORT")
    _p("=" * 65)

    if suspicious:
        # Group by type
        ownership_issues = [s for s in suspicious if "OWNERSHIP" in s]
        change3_issues = [s for s in suspicious if "CHANGE_TYPE_3" in s]
        large_change = [s for s in suspicious if "LARGE_CHANGE" in s]

        if ownership_issues:
            _p(f"\n🔴 High ownership concentration (>80%): {len(ownership_issues)} cases")
            for s in ownership_issues[:10]:
                _p(f"  {s}")

        if change3_issues:
            _p(f"\n🟡 Change type '3' (unknown meaning): {len(change3_issues)} cases")
            _p("     از ۹۴۴K رکورد، ۱۵٬۵۶۰ رکورد change_type=3 دارند")
            _p("     این نوع تغییر در مستندات TSE تعریف نشده است")
            _p("     احتمالاً: خرید اولیه / ورود سهامدار جدید / تغییر کد سهامداری")
            for s in change3_issues[:5]:
                _p(f"  {s}")

        if large_change:
            _p(f"\n🟠 Very large change amounts: {len(large_change)} cases")
            for s in large_change[:5]:
                _p(f"  {s}")

        _p(f"\n📋 Total alerts: {len(suspicious)}")

    else:
        _p("\n✅ No suspicious patterns detected in the sampled data.")

    _p(f"\n{'='*65}")
    _p(f"⏱ Total time: {time.monotonic() - t0:.1f}s")


async def _ensure_constraint(session) -> None:
    """Check that the UNIQUE constraint exists on (symbol, shareholder_name, date).

    If missing, add it — this makes ON CONFLICT DO NOTHING actually work
    and prevents duplicate rows on re-run.
    """
    from sqlalchemy import text

    # Check if constraint already exists
    r = await session.execute(
        text("""
            SELECT 1 FROM pg_constraint
            WHERE conname = 'uq_shareholder_record'
              AND conrelid = 'brsapi_shareholder_records'::regclass
        """)
    )
    exists = r.fetchone() is not None

    if exists:
        _p("  ✅ UNIQUE constraint `uq_shareholder_record` already exists")
        return

    # Remove any existing duplicates before adding the constraint
    _p("  ⚠️  Constraint not found — cleaning duplicates first...")
    r = await session.execute(
        text("""
            DELETE FROM brsapi_shareholder_records
            WHERE id IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY symbol, shareholder_name, COALESCE(date, '')
                        ORDER BY id
                    ) AS rn
                    FROM brsapi_shareholder_records
                ) sub
                WHERE rn > 1
            )
        """)
    )
    removed = r.rowcount
    if removed:
        _p(f"     Removed {removed} duplicate rows")

    # Add the constraint
    await session.execute(
        text("""
            ALTER TABLE brsapi_shareholder_records
            ADD CONSTRAINT uq_shareholder_record
            UNIQUE (symbol, shareholder_name, date)
        """)
    )
    await session.commit()
    _p("  ✅ UNIQUE constraint `uq_shareholder_record` added successfully")
    _p("     -> ON CONFLICT DO NOTHING will now prevent duplicates")


async def _flush_batch(session, batch: list[dict[str, Any]]) -> None:
    """Bulk-insert a batch of shareholder records.

    Builds a single multi-row INSERT statement (one round-trip per batch).
    """
    from sqlalchemy import text

    time.strftime("%Y-%m-%d %H:%M:%S")

    # Build VALUES tuples:  ((symbol, name, ...), (...), ...)
    values_placeholders = []
    params: dict[str, Any] = {}
    for i, row in enumerate(batch):
        p = i * 10
        params[f"sym{p}"] = row["symbol"]
        params[f"nam{p}"] = row["shareholder_name"]
        params[f"vol{p}"] = row["shares"]
        params[f"pct{p}"] = row["percent"]
        params[f"chg{p}"] = row["change_type"]
        params[f"dat{p}"] = _format_date(row["date_str"])
        params[f"sid{p}"] = row["stock_id"]
        values_placeholders.append(
            f"(:sym{p}, :nam{p}, :vol{p}, :pct{p}, :chg{p}, :dat{p}, :sid{p}, NOW())"
        )

    stmt = """
        INSERT INTO brsapi_shareholder_records
            (symbol, shareholder_name, volume, percent, change, date, ins_id, created_at)
        VALUES
    """ + ",\n".join(values_placeholders) + "\nON CONFLICT DO NOTHING"

    await session.execute(text(stmt), params)


if __name__ == "__main__":
    import asyncio

    asyncio.run(run())
