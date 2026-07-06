#!/usr/bin/env python3
"""
Standalone script to test TSETMC API connectivity.
No Docker, no database needed - just checks if the APIs respond.

Usage:
    python test_tsetmc_api.py
"""
from __future__ import annotations

import asyncio
import sys
import json

import httpx

TSETMC_CDN = "https://cdn.tsetmc.com/api"
TSETMC_OLD = "http://old.tsetmc.com"

ENDPOINTS = [
    ("Instrument List", f"{TSETMC_CDN}/Instrument/GetInstrumentList"),
    ("Market Data", f"{TSETMC_CDN}/MarketData/MarketData"),
    ("Closing Price (sample)", f"{TSETMC_CDN}/ClosingPrice/GetClosingPriceHistory/43362635835198978"),
    ("Order Book (sample)", f"{TSETMC_CDN}/OrderBook/GetOrderBook/43362635835198978"),
    ("Old Market Watch", f"{TSETMC_OLD}/tsev2/data/MarketWatchPlus.aspx"),
]


async def _test_endpoint(name: str, url: str) -> bool:  # noqa: pytest - helper, not a test
    """Test a single endpoint and print the result."""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url)
            size = len(resp.content)
            if resp.status_code == 200:
                print(f"  ✅ {name}: HTTP {resp.status_code} ({size:,} bytes)")
                # Try to parse first 100 chars of JSON
                if "json" in resp.headers.get("content-type", ""):
                    try:
                        data = resp.json()
                        print(f"       → JSON response ({type(data).__name__})")
                        if isinstance(data, list):
                            print(f"       → {len(data)} items")
                        elif isinstance(data, dict):
                            print(f"       → keys: {list(data.keys())[:5]}")
                    except Exception:
                        print(f"       → Text preview: {resp.text[:100]}")
                else:
                    print(f"       → Preview: {resp.text[:80]}")
                return True
            else:
                print(f"  ⚠️  {name}: HTTP {resp.status_code} ({size:,} bytes)")
                return False
    except httpx.TimeoutException:
        print(f"  ❌ {name}: TIMEOUT")
        return False
    except httpx.ConnectError as e:
        print(f"  ❌ {name}: CONNECTION FAILED - {e}")
        return False
    except Exception as e:
        print(f"  ❌ {name}: {type(e).__name__}: {e}")
        return False


async def main():
    print("=" * 60)
    print("  TSETMC API Connectivity Test")
    print("=" * 60)
    print()

    results = {}
    for name, url in ENDPOINTS:
        results[name] = await _test_endpoint(name, url)

    print()
    print("─" * 60)
    passed = sum(1 for v in results.values() if v)
    failed = len(results) - passed
    print(f"  Results: {passed}/{len(results)} passed, {failed}/{len(results)} failed")

    if passed == len(results):
        print("  🎉 All TSETMC endpoints are reachable!")
        print()
        print("  Next steps:")
        print("    1. Start Docker services:  docker compose up -d postgres timescaledb redis minio")
        print("    2. Run ingestion:          python -m ingestion.main")
    elif passed > 0:
        print(f"  ⚠️  {failed} endpoint(s) failed but some are working.")
        print("     The ingestion system will use the ones that work.")
    else:
        print("  ❌ All TSETMC endpoints failed.")
        print()
        print("  Possible issues:")
        print("    - VPN may be required to access TSETMC from outside Iran")
        print("    - TSETMC CDN may have changed its endpoints")
        print("    - Check your internet connection")

    print("=" * 60)
    return 0 if passed > 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
