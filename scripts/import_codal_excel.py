# -*- coding: utf-8 -*-
# ruff: noqa
"""Fast bulk importer for Codal Excel financial statements into database."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

CODAL_DIR = PROJECT_ROOT / "data brsapi" / "codal_excel_files"
CHECKPOINT = PROJECT_ROOT / "scripts" / ".codal_import_checkpoint.json"
BATCH_SIZE = 500  # records per DB transaction

PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
ASCII_DIGITS = "0123456789"
_TRANS = str.maketrans(PERSIAN_DIGITS + ARABIC_DIGITS, ASCII_DIGITS * 2)

FINANCIAL_KEYWORDS = {
    "revenue": ["فروش", "درآمد فروش", "فروش خالص", "فروش محصولات"],
    "cogs": ["بهای تمام شده", "هزینه تولید"],
    "gross_profit": ["سود ناخالص"],
    "operating_profit": ["سود عملیاتی"],
    "net_profit": ["سود خالص", "سود پس از ماليات", "سود (زيان) خالص"],
    "eps": ["سود هر سهم", "سود (زيان) هر سهم", "EPS", "eps"],
    "total_assets": ["جمع داراييها", "جمع داراییها", "کل داراییها"],
    "total_liabilities": ["جمع بدهيها", "جمع بدهیها"],
    "equity": ["جمع حقوق صاحبان سهام"],
    "capital": ["سرمايه ثبت شده", "سرمایه ثبت شده"],
    "operating_cash_flow": ["نقد حاصل از عمليات", "نقد حاصل از عملیات"],
}


def _norm(text: str) -> float:
    if not text or not isinstance(text, str):
        return 0.0
    t = text.strip().replace(",", "").replace("٬", "").translate(_TRANS)
    t = re.sub(r"[^\d\-\.]", "", t)
    try:
        return float(t) if t else 0.0
    except ValueError:
        return 0.0


def _parse_fname(name: str) -> dict | None:
    name = name.replace(".xlsx", "").replace(".xls", "")
    parts = name.split("_")
    if len(parts) < 2:
        return None
    return {"symbol": parts[0], "report_type": parts[1], "date": parts[2] if len(parts) > 2 else ""}


def _file_type(fp: str) -> str:
    try:
        with open(fp, "rb") as f:
            h = f.read(16)
        if h[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            return "xls"
        if h[:4] == b"PK\x03\x04":
            return "xlsx"
        return "html"
    except Exception:
        return "unknown"


def _extract_items(tables: list) -> dict:
    result = {}
    for tbl in tables:
        for row in tbl:
            if not row or not row[0]:
                continue
            label = str(row[0]).strip().lower()
            for key, kws in FINANCIAL_KEYWORDS.items():
                if key in result:
                    continue
                for kw in kws:
                    if kw.lower() in label:
                        for cell in row[1:]:
                            v = _norm(str(cell))
                            if v != 0:
                                result[key] = v
                                break
    return result


def _parse_html(filepath: str) -> dict:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return {"error": "bs4 not installed"}

    content = None
    for enc in ("utf-8-sig", "utf-8", "cp1256", "latin-1"):
        try:
            with open(filepath, "r", encoding=enc) as f:
                content = f.read()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    if not content:
        return {"error": "Cannot read"}

    soup = BeautifulSoup(content, "html.parser")
    title = (soup.find("title") or type("", (), {"get_text": lambda *a, **k: ""})()).get_text(strip=True)
    rows = soup.find_all("tr")
    tables, cur = [], []
    for row in rows:
        cells = row.find_all(["td", "th"])
        rd = [c.get_text(strip=True, separator=" ") for c in cells]
        if not any(c.strip() for c in rd):
            if cur:
                tables.append(cur)
                cur = []
            continue
        cur.append(rd)
    if cur:
        tables.append(cur)

    return {
        "title": title,
        "table_count": len(tables),
        "raw_rows_count": len(rows),
        "financial_items": _extract_items(tables),
        "tables": [{"headers": t[0], "rows": t[1:]} for t in tables],
    }


def _parse_xls(filepath: str) -> dict:
    try:
        import xlrd
    except ImportError:
        return {"error": "xlrd not installed. pip install xlrd==1.2.0"}

    try:
        wb = xlrd.open_workbook(filepath, formatting_info=False)
    except Exception as e:
        return {"error": str(e)}

    tables, all_rows = [], []
    for sn in wb.sheet_names():
        ws = wb.sheet_by_name(sn)
        sheet_rows = []
        for r in range(ws.nrows):
            row = [str(ws.cell_value(r, c)) if ws.cell_value(r, c) else "" for c in range(ws.ncols)]
            sheet_rows.append(row)
            all_rows.append(row)
        cur = []
        for row in sheet_rows:
            if not any(c.strip() for c in row if c):
                if cur:
                    tables.append(cur)
                    cur = []
                continue
            cur.append(row)
        if cur:
            tables.append(cur)

    title = ""
    for row in all_rows[:10]:
        for cell in row:
            if cell and len(str(cell)) > 10:
                title = str(cell).strip()
                break
        if title:
            break

    return {
        "title": title,
        "table_count": len(tables),
        "raw_rows_count": len(all_rows),
        "financial_items": _extract_items(tables),
        "tables": [{"headers": t[0], "rows": t[1:]} for t in tables],
    }


# ── Checkpoint ──────────────────────────────────────────────────────────────

def _load_checkpoint() -> set:
    if CHECKPOINT.exists():
        try:
            return set(json.loads(CHECKPOINT.read_text("utf-8")).get("done", []))
        except Exception:
            pass
    return set()


def _save_checkpoint(done: set):
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT.write_text(json.dumps({"done": sorted(done)}, ensure_ascii=False), "utf-8")


# ── Main ────────────────────────────────────────────────────────────────────

def run_import():
    import asyncio
    import core.database as db

    if not CODAL_DIR.exists():
        print(f"Directory not found: {CODAL_DIR}")
        return

    # Scan all files
    all_files = []
    for company in sorted(CODAL_DIR.iterdir()):
        if not company.is_dir():
            continue
        for f in company.iterdir():
            if f.suffix.lower() in (".xlsx", ".xls"):
                all_files.append(str(f))

    total = len(all_files)
    done_set = _load_checkpoint()
    remaining = [f for f in all_files if f not in done_set]
    print(f"Total files: {total:,} | Already imported: {len(done_set):,} | Remaining: {len(remaining):,}")

    if not remaining:
        print("Nothing to import.")
        return

    async def _go():
        await db.init_database()

        # Create table
        async with db.async_session_factory() as s:
            await s.execute(__import__("sqlalchemy").text("""
                CREATE TABLE IF NOT EXISTS codal_financial_statements (
                    id VARCHAR(50) PRIMARY KEY,
                    symbol VARCHAR(50) NOT NULL,
                    report_type VARCHAR(20),
                    report_date VARCHAR(20),
                    filename VARCHAR(200),
                    file_path TEXT,
                    title TEXT,
                    parsed_data JSONB,
                    table_count INTEGER DEFAULT 0,
                    row_count INTEGER DEFAULT 0,
                    import_batch VARCHAR(50),
                    imported_at TIMESTAMP DEFAULT NOW(),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            for idx_name in ["idx_cfs_symbol", "idx_cfs_report_type", "idx_cfs_report_date", "idx_cfs_import_batch"]:
                await s.execute(__import__("sqlalchemy").text(f"""
                    CREATE INDEX IF NOT EXISTS {idx_name} ON codal_financial_statements(
                        {'symbol' if 'symbol' in idx_name else 'report_type' if 'type' in idx_name else 'report_date' if 'date' in idx_name else 'import_batch'}
                    )
                """))
            await s.execute(__import__("sqlalchemy").text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_cfs_std ON codal_financial_statements(symbol, report_type, report_date)
            """))
            await s.commit()

        batch_id = f"import_{int(time.time())}"
        imported = 0
        errors = 0
        t0 = time.time()

        # Process in chunks
        for chunk_start in range(0, len(remaining), BATCH_SIZE):
            chunk = remaining[chunk_start:chunk_start + BATCH_SIZE]
            records = []

            for fp in chunk:
                try:
                    meta = _parse_fname(os.path.basename(fp))
                    if not meta:
                        done_set.add(fp)
                        continue

                    ft = _file_type(fp)
                    if ft == "xls":
                        parsed = _parse_xls(fp)
                    else:
                        parsed = _parse_html(fp)

                    if "error" in parsed:
                        # Still save metadata even if parse fails
                        parsed = {"error": parsed["error"], "title": "", "financial_items": {}, "tables": [], "table_count": 0, "raw_rows_count": 0}

                    raw_key = f"{meta['symbol']}_{meta['report_type']}_{meta['date']}"
                    new_id = "cfs_" + hashlib.md5(raw_key.encode()).hexdigest()[:16]
                    records.append({
                        "id": new_id,
                        "symbol": meta["symbol"],
                        "rt": meta["report_type"],
                        "rd": meta["date"],
                        "fn": os.path.basename(fp),
                        "fp": fp,
                        "title": parsed.get("title", "")[:500],
                        "data": json.dumps(parsed, ensure_ascii=False, default=str),
                        "tc": parsed.get("table_count", 0),
                        "rc": parsed.get("raw_rows_count", 0),
                        "batch": batch_id,
                    })
                    done_set.add(fp)
                    imported += 1
                except Exception as e:
                    errors += 1
                    done_set.add(fp)

            # Bulk upsert
            if records:
                async with db.async_session_factory() as s:
                    from sqlalchemy import text
                    for rec in records:
                        await s.execute(text("""
                            INSERT INTO codal_financial_statements
                            (id, symbol, report_type, report_date, filename, file_path, title, parsed_data, table_count, row_count, import_batch, imported_at)
                            VALUES (:id, :sym, :rt, :rd, :fn, :fp, :title, :data, :tc, :rc, :batch, NOW())
                            ON CONFLICT (symbol, report_type, report_date)
                            DO UPDATE SET
                                parsed_data = EXCLUDED.parsed_data,
                                filename = EXCLUDED.filename,
                                file_path = EXCLUDED.file_path,
                                title = EXCLUDED.title,
                                table_count = EXCLUDED.table_count,
                                row_count = EXCLUDED.row_count,
                                import_batch = EXCLUDED.import_batch
                        """), rec)
                    await s.commit()

            # Progress
            elapsed = time.time() - t0
            done_total = chunk_start + len(chunk)
            pct = done_total / len(remaining) * 100
            rate = done_total / max(elapsed, 0.1)
            eta = (len(remaining) - done_total) / max(rate, 0.1) / 60
            print(f"[{done_total:,}/{len(remaining):,}] {pct:.1f}% | OK:{imported:,} ERR:{errors} | {rate:.0f}/s | ETA:{eta:.0f}m")

            # Save checkpoint every 2000
            if (chunk_start // BATCH_SIZE) % 4 == 0:
                _save_checkpoint(done_set)

        _save_checkpoint(done_set)
        elapsed = time.time() - t0
        print(f"\nDone: {imported:,} imported, {errors} errors in {elapsed:.0f}s ({elapsed/60:.1f}m)")

    asyncio.run(_go())


def show_stats():
    import asyncio
    import core.database as db

    async def _s():
        await db.init_database()
        from sqlalchemy import text
        async with db.async_session_factory() as s:
            r = await s.execute(text("SELECT COUNT(*) FROM codal_financial_statements"))
            print(f"Total records: {r.scalar():,}")
            r = await s.execute(text("SELECT COUNT(DISTINCT symbol) FROM codal_financial_statements"))
            print(f"Companies: {r.scalar():,}")
            r = await s.execute(text("SELECT report_type, COUNT(*) FROM codal_financial_statements GROUP BY report_type ORDER BY 2 DESC"))
            print("\nBy report type:")
            for row in r.fetchall():
                print(f"  {row[0]}: {row[1]:,}")
            r = await s.execute(text("SELECT symbol, COUNT(*) FROM codal_financial_statements GROUP BY symbol ORDER BY 2 DESC LIMIT 10"))
            print("\nTop 10:")
            for row in r.fetchall():
                print(f"  {row[0]}: {row[1]:,}")

    asyncio.run(_s())


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "import"
    if cmd == "stats":
        show_stats()
    elif cmd == "reset":
        if CHECKPOINT.exists():
            CHECKPOINT.unlink()
            print("Checkpoint cleared.")
        run_import()
    else:
        run_import()
