"""Profile all market endpoints — measure response time, cache hit/miss, DB queries."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"
TIMEOUT = 30  # seconds per request

# All market-related endpoints to profile
ENDPOINTS = [
    # ── Core Market ──
    ("market:overview", "/market/overview"),
    ("market:indices", "/market/indices"),
    ("market:gainers-10", "/market/gainers?limit=10"),
    ("market:gainers-20", "/market/gainers?limit=20"),
    ("market:losers-10", "/market/losers?limit=10"),
    ("market:active-10", "/market/active?limit=10"),
    ("market:watch", "/market/watch"),
    # ── Visual ──
    ("market:heatmap", "/market/heatmap"),
    ("market:enriched-heatmap", "/market/enriched-heatmap"),
    ("market:treemap", "/market/treemap?limit=500"),
    # ── Sparklines (need symbols) ──
    ("market:sparklines-5", "/market/sparklines?symbols=fولاد,فملی,خودرو,شپنا,فخوز&limit=30"),
    (
        "market:sparklines-20",
        "/market/sparklines?symbols=fولاد,فملی,خودرو,شپنا,فخوز,خساپا,وبملت,کگل,فولاد,شبندر,ℋyr,hpfix,hmfix,شستا, galer, همراه,スマート,ollr,oilr&limit=30",
    ),
    # ── Aggregate ──
    ("dashboard", "/market-dashboard"),
    ("market-watch", "/market-watch?market=all"),
    # ── Per-symbol ──
    ("market:candles", "/market/candles/fولاد?type=3&limit=30"),
    ("market:history", "/market/history/fولاد?limit=50"),
    ("market:indicator-rsi", "/market/indicator/fولاد?indicator=rsi&period=14"),
    # ── Health (baseline) ──
    ("health", "/health"),
]


def fetch(name: str, path: str) -> dict:
    """Fetch a single endpoint, return timing data."""
    url = f"{BASE}{path}"
    start = time.monotonic()
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = resp.read()
            elapsed_ms = (time.monotonic() - start) * 1000
            status = resp.status
            size = len(data)
            # Parse to check success
            try:
                body = json.loads(data)
                success = body.get("success", True)
            except Exception:
                success = True
            return {
                "name": name,
                "path": path,
                "status": status,
                "success": success,
                "elapsed_ms": round(elapsed_ms, 1),
                "size_bytes": size,
            }
    except urllib.error.HTTPError as e:
        elapsed_ms = (time.monotonic() - start) * 1000
        return {
            "name": name,
            "path": path,
            "status": e.code,
            "success": False,
            "elapsed_ms": round(elapsed_ms, 1),
            "size_bytes": 0,
            "error": str(e),
        }
    except Exception as e:
        elapsed_ms = (time.monotonic() - start) * 1000
        return {
            "name": name,
            "path": path,
            "status": 0,
            "success": False,
            "elapsed_ms": round(elapsed_ms, 1),
            "size_bytes": 0,
            "error": str(e),
        }


def main():
    print("=" * 70)
    print("  MARKET ENDPOINT PROFILING — Round 1 (Cold / First Call)")
    print("=" * 70)
    print(f"{'Name':<25} {'Status':>6} {'Time(ms)':>10} {'Size':>10} {'OK':>4}")
    print("-" * 70)

    results = []
    for name, path in ENDPOINTS:
        r = fetch(name, path)
        results.append(r)
        status_str = f"{r['status']}" if r["status"] else "ERR"
        ok_str = "OK" if r["success"] else "FAIL"
        print(f"{r['name']:<25} {status_str:>6} {r['elapsed_ms']:>9.1f}ms {r['size_bytes']:>9}B {ok_str:>4}")
        if "error" in r:
            print(f"  -> Error: {r['error'][:80]}")

    # ── Round 2: Cache hits ──
    print()
    print("=" * 70)
    print("  MARKET ENDPOINT PROFILING — Round 2 (Cache Warm)")
    print("=" * 70)
    print(f"{'Name':<25} {'Status':>6} {'Time(ms)':>10} {'Size':>10} {'Δ':>8}")
    print("-" * 70)

    for name, path in ENDPOINTS:
        r2 = fetch(name, path)
        orig = next((r for r in results if r["name"] == name), None)
        delta = 0
        if orig:
            delta = r2["elapsed_ms"] - orig["elapsed_ms"]
        status_str = f"{r2['status']}" if r2["status"] else "ERR"
        delta_str = f"{delta:+.1f}ms"
        print(f"{r2['name']:<25} {status_str:>6} {r2['elapsed_ms']:>9.1f}ms {r2['size_bytes']:>9}B {delta_str:>8}")

    # ── Summary ──
    print()
    print("=" * 70)
    print("  BOTTLENECK ANALYSIS")
    print("=" * 70)

    sorted_results = sorted(results, key=lambda x: x["elapsed_ms"], reverse=True)
    print("\n  Top 5 slowest (first call):")
    for i, r in enumerate(sorted_results[:5], 1):
        print(f"  {i}. {r['name']:<25} {r['elapsed_ms']:>9.1f}ms  ({r['path']})")

    avg_time = sum(r["elapsed_ms"] for r in results) / len(results) if results else 0
    total_size = sum(r["size_bytes"] for r in results)
    print(f"\n  Average response time: {avg_time:.1f}ms")
    print(f"  Total payload size: {total_size / 1024:.1f}KB")

    # Identify bottlenecks (>500ms = slow, >2000ms = critical)
    slow = [r for r in results if r["elapsed_ms"] > 500]
    critical = [r for r in results if r["elapsed_ms"] > 2000]
    print(f"\n  Slow (>500ms): {len(slow)} endpoints")
    print(f"  Critical (>2s): {len(critical)} endpoints")
    if slow:
        print("\n  ⚠️  Slow endpoints:")
        for r in slow:
            print(f"    - {r['name']}: {r['elapsed_ms']}ms")


if __name__ == "__main__":
    main()
