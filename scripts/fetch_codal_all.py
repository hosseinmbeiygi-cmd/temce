"""
Fetch CODAL announcements + download attached files.

Usage:
    python scripts/fetch_codal_all.py

Storage:
  - codal_data/{symbol}_codal.json  -- announcements (links + text)
  - codal_data/downloads/           -- downloaded PDF/Excel files
"""
import json
import os
import sys
import time

import requests

# ============================================================
# Load API key from .env or environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ.get("BRSAPI_API_KEY", "")
BASE_URL = "https://api.brsapi.ir/Codal/Announcement.php"
CODEAL_BASE = "https://www.codal.ir"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}
OUTPUT_DIR = "codal_data"
DOWNLOAD_DIR = os.path.join(OUTPUT_DIR, "downloads")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# ============================================================
# Fetch symbol list from database
# ============================================================
def get_symbols_from_db():
    import sys
    sys.path.insert(0, ".")
    import asyncio

    async def _get():
        from core.database import init_database
        await init_database()
        from sqlalchemy import text

        from core.database import async_session_factory
        async with async_session_factory() as s:
            r = await s.execute(text(
                "SELECT DISTINCT symbol FROM instruments WHERE symbol IS NOT NULL AND symbol != '' ORDER BY symbol"
            ))
            return [row[0] for row in r.fetchall()]

    return asyncio.run(_get())


def get_last_dates_from_db():
    import sys
    sys.path.insert(0, ".")
    import asyncio

    async def _get():
        from core.database import init_database
        await init_database()
        from sqlalchemy import text

        from core.database import async_session_factory
        async with async_session_factory() as s:
            r = await s.execute(text("""
                SELECT symbol, MAX(date_publish) as last_date
                FROM codal_reports
                WHERE date_publish IS NOT NULL AND date_publish != ''
                GROUP BY symbol
            """))
            return {row[0]: row[1] for row in r.fetchall()}

    return asyncio.run(_get())


# ============================================================
# Fetch announcements from API
# ============================================================
def fetch_announcements(symbol, date_start, date_end, page=1):
    params = {
        "key": API_KEY,
        "l18": symbol,
        "date_start": date_start,
        "date_end": date_end,
        "page": page,
        "audited": "true",
        "unaudited": "true",
        "only_main_company": "true",
        "only_subsidiaries": "true",
    }
    try:
        resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=180)
        if resp.status_code == 200:
            data = resp.json()
            if not data.get("successful"):
                return None
            return data
        return None
    except Exception:
        return None


def fetch_all_for_symbol(symbol, date_start, date_end):
    all_announcements = []
    page = 1
    total_pages = None

    while True:
        data = fetch_announcements(symbol, date_start, date_end, page)
        if not data:
            break
        if total_pages is None:
            total_pages = data.get("count_page", 1)
        announcements = data.get("announcement", [])
        if not announcements:
            break
        all_announcements.extend(announcements)
        if page >= total_pages:
            break
        page += 1
        time.sleep(0.3)

    return all_announcements


# ============================================================
# Download file from CODAL
# ============================================================
def download_file(url, symbol, announce_id, file_type="pdf"):
    """Download a file from codal.ir and save to downloads/."""
    if not url:
        return None

    # Make absolute URL
    if url.startswith("/"):
        url = CODEAL_BASE + url
    elif not url.startswith("http"):
        return None

    # Create symbol subfolder
    sym_dir = os.path.join(DOWNLOAD_DIR, symbol)
    os.makedirs(sym_dir, exist_ok=True)

    # Determine extension
    ext = ".pdf" if "pdf" in url.lower() or file_type == "pdf" else ".xlsx" if "excel" in url.lower() or file_type == "excel" else ""
    if not ext:
        ext = ".pdf" if file_type == "pdf" else ".xlsx"

    filename = f"{announce_id}{ext}"
    filepath = os.path.join(sym_dir, filename)

    # Skip if already downloaded
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        return filepath

    try:
        resp = requests.get(url, headers=HEADERS, timeout=120, stream=True)
        if resp.status_code == 200:
            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            if os.path.getsize(filepath) > 0:
                return filepath
            else:
                os.remove(filepath)
                return None
        return None
    except Exception:
        return None


# ============================================================
# Save to disk
# ============================================================
def save_json(symbol, records):
    filename = os.path.join(OUTPUT_DIR, f"{symbol}_codal.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    return len(records)


# ============================================================
# Main entry point
# ============================================================
def main():
    try:
        import jdatetime
        today = jdatetime.date.today()
        DATE_END = today.strftime("%Y-%m-%d")
    except ImportError:
        DATE_END = "1405-05-01"

    print("=" * 70)
    print("Fetching CODAL announcements + downloading files")
    print(f"End date: {DATE_END}")
    print("=" * 70)

    symbols = get_symbols_from_db()
    print(f"Total symbols: {len(symbols)}")

    last_dates = get_last_dates_from_db()
    print(f"Symbols in CODAL: {len(last_dates)}")

    # Determine what needs updating
    need_update = []
    for sym in symbols:
        last = last_dates.get(sym)
        if last is None:
            need_update.append((sym, "1400-01-01"))
        else:
            need_update.append((sym, last))

    print(f"Need update: {len(need_update)} symbols")
    print("=" * 70)

    success = 0
    total_records = 0
    total_downloads = 0
    failed = 0

    for idx, (symbol, last_date) in enumerate(need_update, 1):
        print(f"\n[{idx}/{len(need_update)}] {symbol} (since {last_date})...", end=" ", flush=True)

        records = fetch_all_for_symbol(symbol, last_date, DATE_END)

        if records:
            # Enrich with download info
            downloaded = 0
            for ann in records:
                ann_id = ann.get("code", "") or str(hash(ann.get("title", "") + ann.get("date_send", "")))

                # Download PDF if available
                pdf_url = ann.get("link_pdf", "")
                if pdf_path := download_file(pdf_url, symbol, ann_id, "pdf"):
                    ann["local_pdf"] = pdf_path
                    downloaded += 1

                # Download Excel if available
                excel_url = ann.get("link_excel", "")
                if excel_path := download_file(excel_url, symbol, ann_id, "excel"):
                    ann["local_excel"] = excel_path
                    downloaded += 1

                # Download attachment if available
                att_url = ann.get("link_attachment", "")
                if att_url and not pdf_url and not excel_url:
                    if att_path := download_file(att_url, symbol, ann_id, "pdf"):
                        ann["local_attachment"] = att_path
                        downloaded += 1

            n = save_json(symbol, records)
            print(f"OK {n} announcements, {downloaded} files downloaded")
            success += 1
            total_records += n
            total_downloads += downloaded
        else:
            print("No data")
            failed += 1

        time.sleep(0.3)

    print("\n" + "=" * 70)
    print("Done!")
    print(f"{success} symbols with data")
    print(f"{failed} symbols without data")
    print(f"Total announcements: {total_records}")
    print(f"Total files downloaded: {total_downloads}")
    print(f"Announcements dir: {OUTPUT_DIR}/")
    print(f"Files dir: {DOWNLOAD_DIR}/")
    print("=" * 70)
    print("\nNow click 'Import CODAL announcements' on the Brsapi frontend page.")


if __name__ == "__main__":
    main()
