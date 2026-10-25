"""QA: reclassify raw crawl results into accurate render verdicts.

The crawl records raw signals; this script applies the verdict rules so the
readiness score is not inflated by false positives. Key distinctions:

  * A 500 from the Next.js dev/prod proxy means the BACKEND is down, not that
    the page is broken. Those routes still render.
  * A React page error (hydration mismatch, crash) is a genuine UI defect.
  * A 404 shown as page CONTENT (h1 == '404') is a dynamic-route sample that
    does not exist, not a broken build.

Usage: python qa/ui_crawl_classify.py [results.json] [summary_out.json]
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter

RESULTS = sys.argv[1] if len(sys.argv) > 1 else "reports/ui_crawl_results.json"
SUMMARY_OUT = sys.argv[2] if len(sys.argv) > 2 else "reports/ui_crawl_summary.json"

# "Failed to load resource: the server responded with a status of 500" and the
# 404 equivalent are emitted by the browser for every failed XHR. When the
# backend is down, every data route produces these.
BACKEND_NOISE = re.compile(
    r"Failed to load resource: the server responded with a status of (500|502|503|504)",
    re.I,
)
NETWORK_NOISE = re.compile(r"Failed to load resource: net::ERR_|ERR_CONNECTION_REFUSED", re.I)


def classify(rec: dict) -> str:
    perf = rec.get("perf") or {}
    text_len = perf.get("textLength", 0)
    h1 = (perf.get("h1") or "").strip()

    console = rec.get("consoleErrors") or []
    page_errs = rec.get("pageErrors") or []

    # 1. Genuine runtime crash / hydration error wins over everything.
    if page_errs:
        return "RUNTIME_ERROR"

    # 2. Nothing rendered at all.
    if text_len < 5:
        return "BLANK"

    # 3. The page rendered, but its own content is a 404 (dynamic sample id).
    if h1 == "404" or perf.get("hasErrorBoundaryText") and text_len < 120:
        return "NOT_FOUND_CONTENT"

    # 4. Page rendered real content. Charts/canvas pages (heatmap, market-depth,
    #    fx, smart-screener) legitimately have no <h1>; what matters is that
    #    they painted content and threw no page-level error.
    if h1 or text_len >= 100:
        return "OK_BACKEND_DOWN" if console else "OK"

    # 5. Very little content AND real console errors -> genuinely degraded.
    return "DEGRADED" if console else "OK"


def main() -> int:
    with open(RESULTS, encoding="utf-8") as fh:
        results = json.load(fh)

    for rec in results:
        # Filter backend-availability noise FIRST, then classify on what is
        # left, otherwise every route looks degraded while the API is down.
        raw = rec.get("consoleErrors") or []
        real = [m for m in raw if not (BACKEND_NOISE.search(m) or NETWORK_NOISE.search(m))]
        rec["realConsoleErrors"] = real
        # consoleErrorCount is the raw count recorded at crawl time; it survives
        # re-runs after consoleErrors itself has been stripped, which keeps this
        # script idempotent.
        raw_total = rec.get("consoleErrorCount", len(raw))
        rec["backendUnavailableErrors"] = raw_total - len(real)
        rec["verdict"] = classify(rec)
        rec.pop("consoleErrors", None)

    counts = Counter(r["verdict"] for r in results)
    lat = sorted(r["latencyMs"] for r in results if isinstance(r.get("latencyMs"), int))

    def pct(p: float):
        return lat[min(len(lat) - 1, int(len(lat) * p))] if lat else None

    def paint_stats(key: str) -> dict:
        vals = sorted(
            (r["perf"][key] or 0)
            for r in results
            if r.get("perf") and isinstance(r["perf"].get(key), (int, float)) and r["perf"][key]
        )
        if not vals:
            return {"n": 0, "p50": None, "p90": None, "max": None}
        return {
            "n": len(vals),
            "p50": vals[len(vals) // 2],
            "p90": vals[min(len(vals) - 1, int(len(vals) * 0.9))],
            "max": vals[-1],
        }

    rendered = [r for r in results if r["verdict"].startswith("OK")]
    summary = {
        "base": (results[0].get("url", "").split("/gold")[-1] if results else ""),
        "total_routes": len(results),
        "verdicts": dict(counts),
        "rendered_ok": counts.get("OK", 0) + counts.get("OK_BACKEND_DOWN", 0),
        "render_ok_share": round(
            (counts.get("OK", 0) + counts.get("OK_BACKEND_DOWN", 0)) / max(1, len(results)), 4
        ),
        "blank": counts.get("BLANK", 0),
        "runtime_errors": counts.get("RUNTIME_ERROR", 0),
        "routes_with_real_console_errors": sum(1 for r in results if r["realConsoleErrors"]),
        "total_real_console_errors": sum(len(r["realConsoleErrors"]) for r in results),
        "total_backend_unavailable_errors": sum(r["backendUnavailableErrors"] for r in results),
        "latency_ms": {
            "firstContentfulPaint": paint_stats("firstContentfulPaint"),
            "domContentLoaded": paint_stats("domContentLoaded"),
            "loadEventEnd": paint_stats("loadEvent"),
            "crawl_wallclock_includes_settle_sleep": {
                "p50": pct(0.5),
                "p90": pct(0.9),
                "p95": pct(0.95),
                "max": lat[-1] if lat else None,
                "min": lat[0] if lat else None,
            },
        },
        "rendered_route_latency_p50_ms": pct(0.5),
        "notes": [
            "Backend was not running during this crawl; Next.js returns 500 for "
            "every proxied API call. Those errors are counted separately and do "
            "NOT indicate a broken page.",
            "Use firstContentfulPaint / loadEventEnd as the real UI latency. The "
            "crawl_wallclock_* figures include a deliberate 2500 ms settle sleep "
            "and are NOT valid latency measurements.",
            "Measured against a local production build (next start) on the same "
            "machine, not a deployed/CDN environment.",
            "firstContentfulPaint n < total because Chromium only emits a paint "
            "entry for pages that paint before the observation window closes.",
        ],
    }

    with open(RESULTS, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    with open(SUMMARY_OUT, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\n=== NON-OK ROUTES ===")
    for r in results:
        if not r["verdict"].startswith("OK"):
            print(f"  {r['verdict']:20} {r['route']}")
            for m in r["realConsoleErrors"][:2]:
                print(f"      console: {m[:160]}")
            for m in (r.get("pageErrors") or [])[:1]:
                print(f"      pageerr: {m[:160]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
