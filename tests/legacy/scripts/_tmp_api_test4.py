"""Endpoint matrix using the ACTUAL paths the frontend pages call."""

import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://localhost:8000/api/v1"

ENDPOINTS = [
    # Dashboard / market
    ("market/overview", "/market/overview"),
    ("market/gainers", "/market/gainers"),
    ("market/losers", "/market/losers"),
    ("market/active", "/market/active"),
    ("market/enriched-heatmap", "/market/enriched-heatmap"),
    ("market-dashboard", "/market-dashboard"),
    ("market-watch", "/market-watch"),
    ("heatmap page", "/market/enriched-heatmap"),
    # Instruments / symbols
    ("instruments", "/instruments?limit=5"),
    ("instruments/search", "/instruments/search?q=%D9%81%D9%88%D9%84%D8%A7%D8%AF"),
    # Quotes / trades / orderbooks
    ("quotes", "/quotes?limit=5"),
    ("orderbooks/{sym}", "/orderbooks/%D9%81%D9%88%D9%84%D8%A7%D8%AF"),
    ("trades/{sym}", "/trades/%D9%81%D9%88%D9%84%D8%A7%D8%AF?limit=5"),
    # Signals (auth required — expect 401 without token)
    ("signals (auth)", "/signals?limit=5"),
    ("multi-market-signals", "/multi-market-signals?limit=5"),
    ("recommendations", "/recommendations?limit=5"),
    # Screener + AI
    ("screener", "/screener?limit=5"),
    ("screener110/report/market", "/screener110/report/market?limit=3"),
    ("screener110/top-buys", "/screener110/top-buys"),
    ("smart-money/{sym}", "/smart-money/%D9%81%D9%88%D9%84%D8%A7%D8%AF"),
    # Analysis
    ("analysis/overview", "/analysis/overview"),
    ("analysis/liquidity", "/analysis/liquidity"),
    # Fundamental
    ("fundamental/score/{sym}", "/fundamental/score/%D9%81%D9%88%D9%84%D8%A7%D8%AF"),
    ("fundamental/ratios/{sym}", "/fundamental/ratios/%D9%81%D9%88%D9%84%D8%A7%D8%AF"),
    # News / codal / calendar
    ("news", "/news?limit=5"),
    ("news/symbol/{sym}", "/news/symbol/%D9%81%D9%88%D9%84%D8%A7%D8%AF?page_size=5"),
    ("codal", "/codal?limit=5"),
    ("codal/{sym}", "/codal/%D9%81%D9%88%D9%84%D8%A7%D8%AF?page_size=5"),
    ("economic-calendar", "/economic-calendar?limit=5"),
    # Watchlist / alerts / macro
    ("watchlist", "/watchlist"),
    ("alerts", "/alerts?page_size=5"),
    ("macro/", "/macro/"),
    ("brsapi/gold-coin", "/brsapi/gold-coin"),
    ("brsapi/currency", "/brsapi/currency"),
    ("brsapi/crypto", "/brsapi/crypto?limit=5"),
    # Reports
    ("reports/market", "/reports/market"),
    ("reports/symbol/{sym}", "/reports/symbol/%D9%81%D9%88%D9%84%D8%A7%D8%AF"),
    # Admin/ops
    ("alpha", "/alpha"),
    ("tables", "/tables"),
    ("brsapi/sync-status", "/brsapi/sync-status"),
    ("jobs/scheduler", "/jobs/scheduler"),
    # ML
    ("ml/models", "/ml/models"),
    # Options (frontend page /options)
    ("options/strategies", "/options/strategies"),
    ("backtests", "/backtests?limit=5"),
    # Portfolios (auth required)
    ("portfolios (auth)", "/portfolios"),
]

results = []
for name, path in ENDPOINTS:
    url = BASE + path
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "test"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = resp.read(400)
            results.append((name, resp.status, "OK", body[:120]))
    except urllib.error.HTTPError as e:
        body = e.read(300)
        results.append((name, e.code, "ERR", body[:120]))
    except Exception as e:
        results.append((name, "TIMEOUT", str(e)[:80], ""))

print(f"{'ENDPOINT':<38} {'STATUS':<8}")
print("-" * 55)
ok = 0
for name, status, flag, body in results:
    if flag == "OK":
        ok += 1
        print(f"\u2713 {name:<36} {status}")
    elif status in (401,):
        print(f"~ {name:<36} {status} (auth required — by design)")
    elif status in (404, 405):
        print(f"~ {name:<36} {status} (path not found in my test)")
    else:
        print(f"\u2717 {name:<36} {status}")
        print(f"      body: {body!r}")

print(f"\nTOTAL OK: {ok}/{len(results)}")

