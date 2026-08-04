"""Test all frontend pages for HTTP errors and backend API calls."""
import ssl
import urllib.error
import urllib.request

BASE = "http://localhost:3000"

# All pages to test (path, description)
PAGES = [
    ("/", "home"),
    ("/crypto", "crypto-market"),
    ("/crypto-exchange", "crypto-exchange"),
    ("/crypto-market", "crypto-market-alt"),
    ("/news", "news"),
    ("/admin", "admin"),
    ("/macro", "macro"),
    ("/brsapi", "brsapi-dashboard"),
    ("/brsapi/codal", "brsapi-codal"),
    ("/brsapi/history/فولاد", "brsapi-history"),
    ("/heatmap", "market-map"),
    ("/market-watch", "market-watch"),
    ("/analysis", "analysis"),
    ("/analysis/فولاد", "analysis-symbol"),
    ("/screener", "screener"),
    ("/smart-screener", "smart-screener"),
    ("/watchlist", "watchlist"),
    ("/alerts", "alerts"),
    ("/health", "health"),
    ("/tables", "tables"),
    ("/data-import", "data-import"),
    ("/quotes", "quotes"),
    ("/instruments", "instruments"),
    ("/codal", "codal"),
    ("/reports", "reports"),
    ("/risk", "risk"),
    ("/fundamental", "fundamental"),
    ("/trades", "trades"),
    ("/markets", "markets"),
    ("/market-depth", "market-depth"),
    ("/options", "options"),
    ("/funds", "funds"),
    ("/commodities", "commodities"),
    ("/indicators", "indicators"),
    ("/signals", "signals"),
    ("/recommendations", "recommendations"),
    ("/anomalies", "anomalies"),
    ("/holders", "holders"),
    ("/results", "results"),
    ("/portfolio", "portfolio"),
    ("/experiments", "experiments"),
    ("/jobs", "jobs"),
    ("/settings", "settings"),
    ("/chat", "chat"),
    ("/ml", "ml"),
    ("/backtest", "backtest"),
    ("/backtest/generate", "backtest-generate"),
    ("/backtest/engine", "backtest-engine"),
    ("/backtest/cascade", "backtest-cascade"),
    ("/backtest/adaptive", "backtest-adaptive"),
    ("/backtest/decision", "backtest-decision"),
    ("/backtest/methods", "backtest-methods"),
    ("/backtest/compose", "backtest-compose"),
    ("/backtest/monte-carlo", "backtest-monte-carlo"),
    ("/backtest/walk-forward", "backtest-walk-forward"),
    ("/economic-calendar", "economic-calendar"),
    ("/tabdeal-api", "tabdeal-api"),
    ("/tests", "tests"),
    ("/auth/login", "auth-login"),
    ("/auth/register", "auth-register"),
    ("/symbol/فولاد", "symbol-detail"),
    ("/quotes/import", "quotes-import"),
    ("/instruments/import", "instruments-import"),
    ("/codal/import", "codal-import"),
]


def test_page(path, name):
    url = f"{BASE}{path}"
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=30, context=ctx)
        status = resp.getcode()
        size = len(resp.read())
        if status == 200:
            return (path, name, "OK", status, size, None)
        else:
            return (path, name, "WARN", status, size, None)
    except urllib.error.HTTPError as e:
        return (path, name, "ERROR", e.code, 0, str(e.reason))
    except Exception as e:
        return (path, name, "FAIL", 0, 0, str(e)[:100])


if __name__ == "__main__":
    results = []
    total = len(PAGES)
    for i, (path, name) in enumerate(PAGES, 1):
        print(f"[{i}/{total}] Testing {name} ({path})...", end=" ", flush=True)
        r = test_page(path, name)
        status_icon = {"OK": "✅", "WARN": "⚠️", "ERROR": "❌", "FAIL": "💥"}.get(r[2], "?")
        print(f"{status_icon} {r[2]} {r[3]} ({r[4]} bytes)")
        if r[5]:
            print(f"       Error: {r[5]}")
        results.append(r)

    # Summary
    ok = sum(1 for r in results if r[2] == "OK")
    warns = sum(1 for r in results if r[2] == "WARN")
    errors = sum(1 for r in results if r[2] == "ERROR")
    fails = sum(1 for r in results if r[2] == "FAIL")

    print(f"\n{'='*60}")
    print(f"RESULTS: {ok} OK, {warns} warnings, {errors} errors, {fails} failures / {total} total")
    print(f"{'='*60}")

    if errors + fails > 0:
        print("\nFailed pages:")
        for r in results:
            if r[2] in ("ERROR", "FAIL"):
                print(f"  ❌ {r[1]} ({r[0]}) -> {r[2]} {r[3]}: {r[5]}")
