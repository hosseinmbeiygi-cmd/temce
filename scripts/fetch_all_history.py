"""
Fetch crypto + gold/currency history from BrsApi.ir.

Usage:
    python scripts/fetch_all_history.py

Then click 'Import from JSON' on the Brsapi page in the frontend.
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
BASE_URL = "https://api.brsapi.ir/Market/Gold_Currency_Pro.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

# Persian date helpers
try:
    import jdatetime
    today = jdatetime.date.today()
    DATE_END = today.strftime("%Y-%m-%d")
except ImportError:
    DATE_END = "1405-05-01"

DATE_START_CRYPTO = "1390-01-01"
DATE_START_GOLD = "1300-01-01"

CRYPTO_DIR = "crypto_history"
HISTORY_DIR = "history_data"
os.makedirs(CRYPTO_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

# ============================================================
# Fetch crypto symbol list
# ============================================================
def fetch_crypto_symbols():
    print("Fetching crypto symbol list...")
    params = {"key": API_KEY, "section": "cryptocurrency"}
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=60)
    data = resp.json()
    symbols = []
    if "cryptocurrency" in data:
        for item in data["cryptocurrency"]:
            if "symbol" in item:
                symbols.append(item["symbol"])
    return sorted(set(symbols))

# ============================================================
# Fetch gold and currency symbol list
# ============================================================
def fetch_gold_currency_symbols():
    print("Fetching gold/currency symbol list...")
    params = {"key": API_KEY, "section": "gold,currency"}
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=60)
    data = resp.json()
    symbols = []
    if "gold" in data:
        for section in ["ounce", "type", "coin", "coin_parsian"]:
            for item in data["gold"].get(section, []):
                if "symbol" in item:
                    symbols.append(item["symbol"])
    if "currency" in data:
        for section in ["free", "sana", "nima"]:
            for item in data["currency"].get(section, []):
                if "symbol" in item:
                    symbols.append(item["symbol"])
    return sorted(set(symbols))

# ============================================================
# Fetch history for a single symbol
# ============================================================
def fetch_history(symbol, date_start=DATE_START_GOLD, date_end=DATE_END):
    params = {
        "key": API_KEY,
        "history": 2,
        "symbol": symbol,
        "date_start": date_start,
        "date_end": date_end,
    }
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=180)
    data = resp.json()
    records = data.get("history_daily") or data.get("result")
    return records if isinstance(records, list) else None

# ============================================================
# Save to disk
# ============================================================
def save_history(output_dir, symbol, records):
    filename = os.path.join(output_dir, f"{symbol}_history.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    return len(records)

# ============================================================
# Main entry point
# ============================================================
def main():
    print("=" * 70)
    print("Fetching history from BrsApi.ir")
    print(f"End date: {DATE_END}")
    print("=" * 70)

    # -- Crypto --
    print("\n" + "=" * 70)
    print("Cryptocurrency")
    print("=" * 70)
    crypto_symbols = fetch_crypto_symbols()
    print(f"Crypto count: {len(crypto_symbols)}")

    crypto_ok = 0
    crypto_rows = 0
    for idx, sym in enumerate(crypto_symbols, 1):
        print(f"  [{idx}/{len(crypto_symbols)}] {sym}...", end=" ", flush=True)
        try:
            records = fetch_history(sym, DATE_START_CRYPTO, DATE_END)
            if records:
                n = save_history(CRYPTO_DIR, sym, records)
                print(f"OK {n} rows")
                crypto_ok += 1
                crypto_rows += n
            else:
                print("No data")
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(0.5)

    print(f"\nCrypto: {crypto_ok}/{len(crypto_symbols)} symbols, {crypto_rows} rows")

    # -- Gold & Currency --
    print("\n" + "=" * 70)
    print("Gold & Currency")
    print("=" * 70)
    gc_symbols = fetch_gold_currency_symbols()
    print(f"Symbol count: {len(gc_symbols)}")

    gc_ok = 0
    gc_rows = 0
    for idx, sym in enumerate(gc_symbols, 1):
        print(f"  [{idx}/{len(gc_symbols)}] {sym}...", end=" ", flush=True)
        try:
            records = fetch_history(sym, DATE_START_GOLD, DATE_END)
            if records:
                n = save_history(HISTORY_DIR, sym, records)
                print(f"OK {n} rows")
                gc_ok += 1
                gc_rows += n
            else:
                print("No data")
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(0.5)

    print(f"\nGold & Currency: {gc_ok}/{len(gc_symbols)} symbols, {gc_rows} rows")

    # -- Summary --
    print("\n" + "=" * 70)
    print("Done!")
    print(f"Crypto: {crypto_rows} rows from {crypto_ok} symbols")
    print(f"Gold & Currency: {gc_rows} rows from {gc_ok} symbols")
    print(f"Total: {crypto_rows + gc_rows} rows")
    print("=" * 70)
    print("\nNow click 'Import from JSON files' on the Brsapi frontend page.")

if __name__ == "__main__":
    main()
