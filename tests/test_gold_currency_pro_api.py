"""
Gold_Currency_Pro API Test — section=gold
============================================

Calls the BrsApi Gold_Currency_Pro endpoint with ``section=gold``,
shows the raw JSON response and the parsed output from
``GoldCurrencyProParser.parse_gold()``.

Usage:
    python tests/test_gold_currency_pro_api.py
    python tests/test_gold_currency_pro_api.py --raw-only   # only raw JSON
    python tests/test_gold_currency_pro_api.py --parsed     # only parsed records
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

import httpx

from brsapi.config import BrsApiEndpoints
from brsapi.parsers.commodity import GoldCurrencyProParser

# ── Config ──────────────────────────────────────
API_KEY = os.getenv("BRSAPI_API_KEY", "")
BASE_URL = "https://Api.BrsApi.ir"
ENDPOINT = BrsApiEndpoints.GOLD_CURRENCY_PRO
SECTION = "gold"


def fetch_gold_currency_pro_section(section: str) -> dict | list | None:
    """Call Gold_Currency_Pro.php with section=gold and return the JSON response."""
    url = f"{BASE_URL}{ENDPOINT.path}"
    params = {"key": API_KEY, "section": section}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    print(f"🌐 GET {url}")
    print(f"   params={params}")
    print()

    try:
        resp = httpx.get(url, params=params, headers=headers, timeout=30)
        print(f"📡 HTTP {resp.status_code} ({len(resp.content)} bytes)")
        print()

        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"❌ HTTP {resp.status_code}: {resp.text[:300]}")
            return None
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Test Gold_Currency_Pro API — section=gold")
    parser.add_argument("--raw-only", action="store_true", help="Only show raw JSON")
    parser.add_argument("--parsed", action="store_true", help="Only show parsed records (hide raw JSON)")
    args = parser.parse_args()

    # ── 1. Fetch ────────────────────────────────
    print("=" * 65)
    print("  Gold_Currency_Pro API Test — section=gold")
    print("=" * 65)
    print()

    data = fetch_gold_currency_pro_section(SECTION)
    if data is None:
        sys.exit(1)

    # ── 2. Show raw response ────────────────────
    if not args.parsed:
        print("📦 RAW RESPONSE")
        print("-" * 65)
        print(json.dumps(data, indent=2, ensure_ascii=False)[:4000])
        print()
        if len(json.dumps(data)) > 4000:
            print(f"  (... truncated, full size: {len(json.dumps(data))} chars)")
            print()

    # ── 3. Parse ─────────────────────────────────
    print("🔧 PARSED — GoldCurrencyProParser.parse_gold()")
    print("-" * 65)

    try:
        records = GoldCurrencyProParser.parse_gold(data)
    except Exception as e:
        print(f"❌ Parse error: {e}")
        sys.exit(1)

    if not records:
        print("  ⚠️  No records parsed")
        sys.exit(0)

    print(f"  ✅ {len(records)} gold item(s) parsed")
    print()

    if not args.raw_only:
        for i, rec in enumerate(records, 1):
            print(f"  [{i}] {rec.get('symbol', '?')}")
            print(f"      name:      {rec.get('name', '')}")
            print(f"      price:     {rec.get('price', 0):,.0f}")
            print(f"      change:    {rec.get('change_value', 0):+,.0f}")
            print(f"      change%:   {rec.get('change_percent', 0):+.2f}%")
            print(f"      unit:      {rec.get('unit', '')}")
            print(f"      date:      {rec.get('date', '')} {rec.get('time', '')}")
            print(f"      section:   {rec.get('section', '')}")
            print(f"      sign:      {rec.get('sign', '')}")
            # Show important Pro-specific fields
            if rec.get("url_base_icon"):
                print(f"      icon:      {rec.get('url_base_icon', '')}{rec.get('path_icon', '')}")
            print()

    # ── 4. Summary ────────────────────────────────
    print("-" * 65)
    prices = [r.get("price", 0) for r in records if r.get("price")]
    if prices:
        print(f"  💰 Price range: {min(prices):,.0f} — {max(prices):,.0f}")
        print(f"  📊 Items with price: {len(prices)}/{len(records)}")
    print("✅ Done")


if __name__ == "__main__":
    main()
