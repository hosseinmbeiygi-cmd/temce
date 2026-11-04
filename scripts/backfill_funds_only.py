"""Backfill funds-only (Option A) — modeled on z.py.

- Allowlist: fund symbols from Postgres (fund_symbol_aliases active + funds.symbol),
  NOT whole AllSymbols.
- JSON-first: raw response saved to funds_data/<endpoint>/<symbol>/<key>.json,
  THEN transferred to Postgres brsapi_* tables (resume-safe, idempotent).
- Rate limits per BrsApi docs (conservative, sequential single-worker):
    Nav 1/10s | Transaction 2/10s | History 4/10s | Candlestick 2/10s
    Shareholder 2/10s | Codal 2/10s | AllSymbols 2/100s
- Checkpoint: funds_backfill_state.json (per endpoint+symbol done flags).

Usage:
    python scripts/backfill_funds_only.py --endpoint all --date latest
    python scripts/backfill_funds_only.py --endpoint nav,history --limit 50
"""
import argparse
import json
import logging
import os
import re
import time
from datetime import datetime

import requests

# کلیدها و رمزها فقط از محیط می‌آیند: fallback هاردکد یعنی لو رفتن در git history.
API_KEY = (os.environ.get("BRSAPI_API_KEY") or os.environ.get("BRSAPI_KEY") or "").strip()
if not API_KEY:
    raise SystemExit("BRSAPI_KEY تنظیم نشده است (در .env بگذارید).")
BASE_URL = "https://api.brsapi.ir"
_PG_PASSWORD = (os.environ.get("PG_PASSWORD") or os.environ.get("DB_PASSWORD") or "").strip()
if not _PG_PASSWORD:
    raise SystemExit("PG_PASSWORD تنظیم نشده است (در .env بگذارید).")
PG = {"host": os.environ.get("PG_HOST", "localhost"), "port": int(os.environ.get("PG_PORT", "5432")),
          "dbname": os.environ.get("PG_DATABASE", "my_first_db"), "user": os.environ.get("PG_USER", "hossein"),
          "password": _PG_PASSWORD}

DATA_DIR = "transactions_data/funds"  # پوشه واحد BrsApi: کنار دیتای z.py (transactions_data/<symbol>/...)
STATE_FILE = "funds_backfill_state.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": USER_AGENT}

# endpoint -> (path, fixed params, sleep seconds between reqs, subdir)
ENDPOINTS = {
    "nav":         ("/Tsetmc/Nav.php", {}, 10.5),
    "transaction": ("/Tsetmc/Transaction.php", {}, 5.5),
    "history0":    ("/Tsetmc/History.php", {"type": "0"}, 3.0),
    "history1":    ("/Tsetmc/History.php", {"type": "1"}, 3.0),
    "candle2":     ("/Tsetmc/Candlestick.php", {"type": "2"}, 5.5),
    "candle3":     ("/Tsetmc/Candlestick.php", {"type": "3"}, 5.5),
    "shareholder": ("/Tsetmc/Shareholder.php", {}, 5.5),
    "codal":       ("/Codal/Announcement.php", {}, 5.5),
}
ALL = ["nav", "transaction", "history0", "history1", "candle2", "candle3", "shareholder", "codal"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.FileHandler("funds_backfill.log", encoding="utf-8"), logging.StreamHandler()])

def safe(s): return re.sub(r'[\\/*?:"<>|]', "", (s or "").strip())

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE, encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_state(st):
    with open(STATE_FILE, "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False, indent=2)

def get_fund_symbols():
    import psycopg2
    conn = psycopg2.connect(**PG)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT symbol FROM fund_symbol_aliases WHERE is_active = TRUE UNION SELECT symbol FROM funds")
    syms = [r[0] for r in cur.fetchall() if r[0] and len(r[0].strip()) >= 2]
    conn.close()
    return sorted(set(syms))

def fetch(path, params, retries=3):
    for i in range(retries):
        try:
            r = requests.get(BASE_URL + path, params={"key": API_KEY, **params}, headers=HEADERS, timeout=20)
            if r.status_code in (429, 403):
                time.sleep(5)
                continue
            if r.status_code == 200:
                return r.json()
            return None
        except Exception as e:
            logging.warning(f"retry {i}: {e}")
            time.sleep(3)
    return None

def transfer_to_pg(endpoint, symbol, data):
    """Stage 2: JSON -> Postgres (best-effort, idempotent). Raw JSON kept as source of truth."""
    if data is None:
        return 0
    try:
        import psycopg2
        conn = psycopg2.connect(**PG)
        conn.autocommit = True
        cur = conn.cursor()
        n = 0
        rows = data if isinstance(data, list) else data.get("data", data)
        if endpoint == "nav" and isinstance(data, dict) and not isinstance(rows, list):
            rows = [data]
        if isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list):
            conn.close()
            return 0
        for it in rows:
            if not isinstance(it, dict):
                continue
            try:
                if endpoint == "nav":
                    cur.execute("INSERT INTO brsapi_nav_records (symbol, nav_issue, nav_redemption, date, raw_json) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        (symbol, float(it.get("nav_issue") or it.get("navIssue") or 0) or None,
                         float(it.get("nav_redemption") or it.get("navRedemption") or 0) or None,
                         str(it.get("date") or datetime.now().strftime("%Y-%m-%d")), json.dumps(it, ensure_ascii=False)))
                    n += 1
                elif endpoint == "transaction":
                    cur.execute("INSERT INTO brsapi_intraday_trades (symbol, row, time, volume, price, trade_date) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        (symbol, int(it.get("row") or 0), str(it.get("time") or ""), int(it.get("volume") or 0), float(it.get("price") or 0), str(it.get("date") or "")))
                    n += 1
                elif endpoint in ("history0",):
                    cur.execute("INSERT INTO brsapi_historical_daily (symbol, date, trade_volume, trade_value, price_min, price_max, price_last, price_close) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        (symbol, str(it.get("date") or ""), int(it.get("trade_volume") or it.get("volume") or 0), float(it.get("trade_value") or it.get("value") or 0),
                         float(it.get("price_min") or it.get("low") or 0), float(it.get("price_max") or it.get("high") or 0),
                         float(it.get("price_last") or it.get("close") or 0), float(it.get("price_close") or it.get("close") or 0)))
                    n += 1
                elif endpoint in ("candle2", "candle3"):
                    ctype = "2" if endpoint == "candle2" else "3"
                    cur.execute("INSERT INTO brsapi_candlesticks (symbol, date, open, high, low, close, volume, candle_type) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        (symbol, str(it.get("date") or ""), float(it.get("open") or 0), float(it.get("high") or 0), float(it.get("low") or 0),
                         float(it.get("close") or 0), float(it.get("volume") or 0), ctype))
                    n += 1
                elif endpoint == "shareholder":
                    cur.execute("INSERT INTO brsapi_shareholder_records (symbol, shareholder_name, volume, percent, date) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        (symbol, str(it.get("shareholder_name") or it.get("name") or ""), float(it.get("volume") or 0), float(it.get("percent") or 0), str(it.get("date") or "")))
                    n += 1
                elif endpoint == "codal":
                    cur.execute("INSERT INTO brsapi_codal_announcements (symbol, title, code, link, raw_json) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        (symbol, str(it.get("title") or "")[:500], str(it.get("code") or ""), str(it.get("link") or ""), json.dumps(it, ensure_ascii=False)))
                    n += 1
            except Exception:
                continue
        conn.close()
        return n
    except Exception as e:
        logging.warning(f"PG transfer skip {endpoint}/{symbol}: {str(e)[:120]}")
        return 0

def run(endpoints, date_str, limit):
    syms = get_fund_symbols()
    if limit:
        syms = syms[:limit]
    logging.info(f"fund symbols: {len(syms)}")
    st = load_state()
    for ep in endpoints:
        path, fixed, sleep_s = ENDPOINTS[ep]
        for sym in syms:
            key = f"{ep}|{sym}|{date_str}"
            out = os.path.join(DATA_DIR, ep, safe(sym), f"{date_str}.json")
            if st.get(key) and os.path.exists(out):
                continue  # resume
            params = {"l18": sym, **fixed}
            if ep == "transaction":
                params["date"] = date_str
            data = fetch(path, params)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            if data is None:
                logging.warning(f"FAIL {ep} {sym}")
                continue
            if isinstance(data, dict) and (data.get("error") or data.get("successful") is False):
                with open(out, "w", encoding="utf-8") as fh:
                    json.dump([], fh, ensure_ascii=False)
                st[key] = "empty"
                save_state(st)
                time.sleep(sleep_s)
                continue
            with open(out, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False)  # stage 1: JSON
            n = transfer_to_pg(ep, sym, data)  # stage 2: PG
            st[key] = f"ok:{n}"
            save_state(st)
            logging.info(f"[{ep}] {sym} -> json + pg:{n}")
            time.sleep(sleep_s)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default="all", help="all | comma list of: " + ",".join(ALL))
    ap.add_argument("--date", default="latest", help="YYYY-MM-DD for transaction, or 'latest'")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    eps = ALL if a.endpoint == "all" else [e.strip() for e in a.endpoint.split(",") if e.strip() in ALL]
    run(eps, a.date, a.limit)
