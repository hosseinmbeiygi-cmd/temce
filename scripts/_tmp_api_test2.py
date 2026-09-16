"""Temp: hit all main API endpoints (correct paths) and report status."""
import contextlib
import json
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://localhost:8000/api/v1"

ENDPOINTS = [
    ("market overview", "/market/overview"),
    ("market indices", "/market/indices"),
    ("market gainers", "/market/gainers"),
    ("market losers", "/market/losers"),
    ("market active", "/market/active"),
    ("market heatmap", "/market/heatmap"),
    ("market enriched-heatmap", "/market/enriched-heatmap"),
    ("market treemap", "/market/treemap"),
    ("market-watch", "/market-watch"),
    ("market-dashboard", "/market-dashboard"),
    ("instruments list", "/instruments?limit=5"),
    ("instruments search", "/instruments/search?q=%D9%81%D9%88%D9%84%D8%A7%D8%AF"),
    ("symbols search", "/symbols/search?q=%D9%81%D9%88%D9%84%D8%A7%D8%AF"),
    ("quotes", "/quotes"),
    ("quotes by symbol", "/quotes?symbol=%D9%81%D9%88%D9%84%D8%A7%D8%AF"),
    ("orderbooks", "/orderbooks"),
    ("trades symbol", "/trades/%D9%81%D9%88%D9%84%D8%A7%D8%AF"),
    ("trades recent", "/trades/%D9%81%D9%88%D9%84%D8%A7%D8%AF/recent"),
    ("recommendations", "/recommendations"),
    ("indicators", "/indicators"),
    ("codal", "/codal"),
    ("news", "/news"),
    ("macro", "/macro"),
    ("fundamental ratios", "/fundamental/ratios/%D9%81%D9%88%D9%84%D8%A7%D8%AF"),
    ("fundamental dcf", "/fundamental/dcf/%D9%81%D9%88%D9%84%D8%A7%D8%AF"),
    ("fundamental score", "/fundamental/score/%D9%81%D9%88%D9%84%D8%A7%D8%AF"),
    ("fundamental industry", "/fundamental/industry/%D9%81%D9%84%D8%B2%D8%A7%D8%AA"),
    ("smart-money symbol", "/smart-money/%D9%81%D9%88%D9%84%D8%A7%D8%AF"),
    ("analysis overview", "/analysis/overview"),
    ("analysis trends", "/analysis/trends"),
    ("analysis liquidity", "/analysis/liquidity"),
    ("analysis elliot", "/analysis/elliot-waves/%D9%81%D9%88%D9%84%D8%A7%D8%AF"),
    ("anomalies", "/anomalies"),
    ("alpha", "/alpha"),
    ("risk", "/risk"),
    ("backtests runs", "/backtests/runs"),
    ("backtests strategies", "/backtests/strategies"),
    ("backtests data/symbols", "/backtests/data/symbols"),
    ("backtests data/stats", "/backtests/data/stats"),
    ("ml models", "/ml/models"),
    ("ml runs", "/ml/runs"),
    ("reports market", "/reports/market"),
    ("reports symbol", "/reports/symbol/%D9%81%D9%88%D9%84%D8%A7%D8%AF"),
    ("funds", "/funds"),
    ("funds types", "/funds/types"),
    ("funds overview", "/funds/overview"),
    ("market-info industries", "/market-info/industries"),
    ("market-info funds", "/market-info/funds"),
    ("brsapi commodities", "/brsapi/commodities"),
    ("brsapi crypto", "/brsapi/crypto"),
    ("brsapi gold-coin", "/brsapi/gold-coin"),
    ("brsapi index", "/brsapi/index"),
    ("screener", "/screener?limit=3"),
    ("screener-v2", "/screener-v2/filter"),
    ("screener110 market", "/screener110/report/market"),
    ("screener110 top-buys", "/screener110/top-buys"),
    ("screener110 symbol", "/screener110/report/%D8%B4%D8%B3%D8%AA%D8%A7"),
    ("economic-calendar", "/economic-calendar"),
    ("market-insights", "/market-insights"),
    ("tables", "/tables"),
    ("options strategies", "/options/strategies"),
    ("options live symbols", "/options/live/symbols"),
    ("tabdeal", "/tabdeal"),
    ("assistant", "/assistant"),
    ("stock-assistant query", "/stock-assistant/query"),
    ("compose", "/compose"),
    ("paper-trading", "/paper-trading"),
    ("saved-filters", "/saved-filters"),
    ("queue-analysis", "/queue-analysis"),
    ("signal-insights", "/signal-insights"),
    ("decision-engine", "/decision-engine"),
]


def call(name, path):
    url = BASE + path
    req = urllib.request.Request(url, method="GET")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            code = resp.status
            has_data = False
            try:
                j = json.loads(raw)
                data = j.get("data") if isinstance(j, dict) else j
                if isinstance(data, dict):
                    has_data = any(
                        isinstance(v, (list, dict)) and len(v) > 0
                        for v in data.values() if v is not None
                    )
                elif isinstance(data, list):
                    has_data = len(data) > 0
            except Exception:
                has_data = len(raw) > 50
            status = f"{code} {'✅' if has_data else '⚠️empty'}"
    except urllib.error.HTTPError as e:
        status = f"{e.code} ❌"
        with contextlib.suppress(Exception):
            status += e.read().decode("utf-8", errors="replace")[:100]
    except Exception as e:
        status = f"❌{type(e).__name__}"
    print(f"{name:<34} {status}")


for name, path in ENDPOINTS:
    call(name, path)
