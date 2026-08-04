"""Fetch crypto history from BrsApi — uses requests exactly like user's tested script."""
import json
import os
import sys
import time

import requests

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
OUTPUT_DIR = "crypto_history"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def fetch_crypto_symbols():
    params = {"key": API_KEY, "section": "cryptocurrency"}
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=60)
    data = resp.json()
    symbols = []
    if "cryptocurrency" in data:
        for item in data["cryptocurrency"]:
            if "symbol" in item:
                symbols.append(item["symbol"])
    return sorted(set(symbols))

def fetch_history(symbol, date_start="1390-01-01", date_end="1405-05-01"):
    params = {"key": API_KEY, "history": 2, "symbol": symbol, "date_start": date_start, "date_end": date_end}
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=180)
    data = resp.json()
    return data.get("history_daily") or data.get("result")

def save_history(symbol, records):
    filename = os.path.join(OUTPUT_DIR, f"{symbol}_history.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    return len(records)

def main():
    symbols = fetch_crypto_symbols()
    print(f"Found {len(symbols)} crypto symbols")
    success = 0
    total = 0
    for idx, symbol in enumerate(symbols, 1):
        print(f"[{idx}/{len(symbols)}] {symbol}...", end=" ", flush=True)
        try:
            records = fetch_history(symbol)
            if records:
                n = save_history(symbol, records)
                print(f"{n} rows")
                success += 1
                total += n
            else:
                print("no data")
        except Exception as e:
            print(f"ERROR: {e}")
        time.sleep(0.5)
    print(f"\nDone: {success}/{len(symbols)} symbols, {total} total rows")

if __name__ == "__main__":
    main()
