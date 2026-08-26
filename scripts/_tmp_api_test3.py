"""Full endpoint status matrix against the running server."""
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://localhost:8000/api/v1"

# (name, path) — GET endpoints the frontend pages depend on
ENDPOINTS = [
    ("market/overview", "/market/overview"),
    ("market/gainers", "/market/gainers"),
    ("market/losers", "/market/losers"),
    ("market/active", "/market/active"),
    ("market/sectors", "/market/sector-summary"),
    ("instruments", "/instruments?limit=5"),
    ("instruments/search", "/instruments/search?q=%D9%81%D9%88%D9%84%D8%A7%D8%AF"),
    ("quotes/list", "/quotes?limit=5"),
    ("quotes/heatmap", "/quotes/heatmap"),
    ("trades/{symbol}", "/trades/%D9%81%D9%88%D9%84%D8%A7%D8%AF?limit=5"),
    ("signals", "/signals?limit=5"),
    ("recommendations", "/recommendations?limit=5"),
    ("screener", "/screener?limit=5"),
    ("screener/filter", "/screener/filter?limit=5"),
    ("screener110/report/market", "/screener110/report/market?limit=3"),
    ("screener110/top-buys", "/screener110/top-buys"),
    ("smart-money/{sym}", "/smart-money/%D9%81%D9%88%D9%84%D8%A7%D8%AF"),
    ("analysis/{sym}", "/analysis/%D9%81%D9%88%D9%84%D8%A7%D8%AF"),
    ("indicators/{sym}", "/indicators/%D9%81%D9%88%D9%84%D8%A7%D8%AF"),
    ("fundamental/{sym}", "/fundamental/%D9%81%D9%88%D9%84%D8%A7%D8%AF"),
    ("news", "/news?limit=5"),
    ("codal", "/codal?limit=5"),
    ("economic-calendar", "/economic-calendar?limit=5"),
    ("alerts", "/alerts?limit=5"),
    ("watchlist", "/watchlist"),
    ("macro", "/macro"),
    ("heatmap", "/heatmap"),
    ("market-dashboard", "/market-dashboard"),
    ("market-watch", "/market-watch"),
    ("funds", "/funds?limit=5"),
    ("brsapi/commodities", "/brsapi/commodities"),
    ("brsapi/crypto", "/brsapi/crypto"),
    ("brsapi/gold-coin", "/brsapi/gold-coin"),
    ("reports/market", "/reports/market"),
    ("reports/symbol", "/reports/symbol/%D9%81%D9%88%D9%84%D8%A7%D8%AF"),
    ("backtests", "/backtests?limit=5"),
    ("options/strategies", "/options/strategies"),
    ("multi-market-signals", "/multi-market-signals?limit=5"),
    ("health", "/health"),
]

results = []
for name, path in ENDPOINTS:
    url = BASE + path
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "test"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read(600)
            results.append((name, resp.status, "OK", body[:150]))
    except urllib.error.HTTPError as e:
        body = e.read(300)
        results.append((name, e.code, "ERR", body[:150]))
    except Exception as e:
        results.append((name, "TIMEOUT/ERR", str(e)[:100], ""))

print(f"{'ENDPOINT':<38} {'STATUS':<8} {'SIZE':<5}")
print("-" * 60)
ok = 0
for name, status, flag, body in results:
    marker = "✓" if flag == "OK" else ("✗" if status not in (404, 405, 307, 308) else "~")
    if flag == "OK":
        ok += 1
    print(f"{marker} {name:<36} {status:<8} {len(body)}")
    if flag == "ERR" and status not in (404, 405):
        print(f"      body: {body!r}")

print(f"\nTOTAL OK: {ok}/{len(results)}")
