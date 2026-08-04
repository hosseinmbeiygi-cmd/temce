"""Test all pages for real data access."""
import json
import ssl
import urllib.error
import urllib.request

BASE_FE = "http://localhost:3000"
BASE_BE = "http://localhost:8000/api/v1"

# Pages that fetch data from API
PAGES = [
    # (path, expected_api, description)
    ("/", "/market-dashboard", "Dashboard"),
    ("/crypto", "/brsapi/crypto", "Crypto"),
    ("/crypto-exchange", "/brsapi/crypto", "Crypto Exchange"),
    ("/news", "/news", "News"),
    ("/admin", "/brsapi/health", "Admin"),
    ("/macro", "/brsapi/currency", "Macro"),
    ("/brsapi", "/brsapi/health", "BrsApi Dashboard"),
    ("/heatmap", "/market/treemap", "Market Map"),
    ("/market-watch", "/brsapi/snapshots", "Market Watch"),
    ("/analysis", "/analysis/overview", "Analysis"),
    ("/screener", "/screener", "Screener"),
    ("/smart-screener", "/screener", "Smart Screener"),
    ("/watchlist", "/watchlist", "Watchlist"),
    ("/alerts", "/alerts", "Alerts"),
    ("/health", "/health", "Health"),
    ("/tables", "/tables", "Tables"),
    ("/quotes", "/quotes", "Quotes"),
    ("/instruments", "/instruments/search?query=f", "Instruments"),
    ("/codal", "/codal", "Codal"),
    ("/reports", "/reports", "Reports"),
    ("/risk", "/risk", "Risk"),
    ("/fundamental", "/fundamental", "Fundamental"),
    ("/trades", "/trades", "Trades"),
    ("/markets", "/market/indices", "Markets"),
    ("/market-depth", "/market/depth", "Market Depth"),
    ("/options", "/tables/brsapi_option_snapshots", "Options"),
    ("/funds", "/tables/brsapi_ime_funds", "Funds"),
    ("/commodities", "/brsapi/commodities", "Commodities"),
    ("/indicators", "/indicators", "Indicators"),
    ("/signals", "/signals", "Signals"),
    ("/recommendations", "/recommendations", "Recommendations"),
    ("/anomalies", "/anomalies", "Anomalies"),
    ("/holders", "/holders", "Holders"),
    ("/results", "/backtest/results", "Results"),
    ("/portfolio", "/portfolio", "Portfolio"),
    ("/experiments", "/experiments", "Experiments"),
    ("/jobs", "/jobs", "Jobs"),
    ("/settings", "/settings", "Settings"),
    ("/chat", "/assistant/capabilities", "Chat"),
    ("/ml", "/ml/models", "ML"),
    ("/backtest", "/backtest/results", "Backtest"),
    ("/economic-calendar", "/economic-calendar", "Economic Calendar"),
    ("/tabdeal-api", "/assistant/capabilities", "Tabdeal API"),
    ("/tests", "/tests", "Tests"),
]

def test_api(url):
    """Test an API endpoint."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10, context=ctx)
        data = json.loads(resp.read())
        if isinstance(data, dict):
            success = data.get("success", True)
            items = data.get("data", {})
            if isinstance(items, dict):
                count = len(items.get("items", [])) if "items" in items else len(items)
            elif isinstance(items, list):
                count = len(items)
            else:
                count = 0
            return True, success, count
        return True, True, 0
    except Exception:
        return False, False, 0

if __name__ == "__main__":
    print("=" * 80)
    print("REAL DATA ACCESS AUDIT")
    print("=" * 80)

    results = []
    for _page_path, api_path, desc in PAGES:
        full_api = f"{BASE_BE}{api_path}"
        ok, success, count = test_api(full_api)
        status = "OK" if ok and success else "FAIL"
        icon = "✅" if status == "OK" else "❌"
        data_info = f"{count} records" if count > 0 else "empty"
        print(f"  {icon} {desc:<20} | {api_path:<40} | {data_info}")
        results.append((desc, api_path, status, count))

    # Summary
    ok_count = sum(1 for r in results if r[2] == "OK")
    fail_count = sum(1 for r in results if r[2] == "FAIL")
    with_data = sum(1 for r in results if r[3] > 0)

    print(f"\n{'=' * 80}")
    print(f"RESULTS: {ok_count} OK, {fail_count} FAIL | {with_data} with data, {len(results) - with_data} empty")
    print(f"{'=' * 80}")

    if fail_count > 0:
        print("\nFailed endpoints:")
        for desc, api, status, _ in results:
            if status == "FAIL":
                print(f"  ❌ {desc}: {api}")
