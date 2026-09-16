"""Temp: hit all main API endpoints and report HTTP status + data presence."""

import contextlib
import json
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://localhost:8000/api/v1"

# (name, path, method, body)
ENDPOINTS = [
    ("market overview", "/market/overview", "GET", None),
    ("market indices", "/market/indices", "GET", None),
    ("market gainers", "/market/gainers", "GET", None),
    ("market losers", "/market/losers", "GET", None),
    ("market active", "/market/active", "GET", None),
    ("market heatmap", "/market/heatmap", "GET", None),
    ("market enriched-heatmap", "/market/enriched-heatmap", "GET", None),
    ("market treemap", "/market/treemap", "GET", None),
    ("market watch", "/market-watch", "GET", None),
    ("instruments", "/instruments?limit=5", "GET", None),
    ("instruments search", "/instruments/search?q=%D9%81%D9%88%D9%84%D8%A7%D8%AF", "GET", None),
    ("quotes", "/quotes?limit=5", "GET", None),
    ("trades", "/trades?limit=5", "GET", None),
    ("signals", "/signals?limit=5", "GET", None),
    ("recommendations", "/recommendations?limit=5", "GET", None),
    ("indicators", "/indicators?limit=5", "GET", None),
    ("news", "/news?limit=5", "GET", None),
    ("codal", "/codal?limit=5", "GET", None),
    ("macro", "/macro", "GET", None),
    ("fundamental", "/fundamental?limit=5", "GET", None),
    ("smart-money", "/smart-money/فولاد", "GET", None),
    ("analysis", "/analysis?symbol=%D9%81%D9%88%D9%84%D8%A7%D8%AF", "GET", None),
    ("backtests", "/backtests?limit=5", "GET", None),
    ("ml", "/ml?limit=5", "GET", None),
    ("multi-market-signals", "/multi-market-signals?limit=5", "GET", None),
    ("reports", "/reports?limit=5", "GET", None),
    ("crypto", "/brsapi/crypto?limit=5", "GET", None),
    ("commodities", "/brsapi/commodities?limit=5", "GET", None),
    ("gold-coin", "/brsapi/gold-coin?limit=5", "GET", None),
    ("funds", "/funds?limit=5", "GET", None),
    ("heatmap page", "/screener?limit=3", "GET", None),
    ("screener110 report", "/screener110/report/شستا", "GET", None),
    ("screener110 market report", "/screener110/report/market", "GET", None),
    ("screener110 top-buys", "/screener110/top-buys", "GET", None),
    ("anomalies", "/anomalies?limit=5", "GET", None),
    ("options", "/options?limit=5", "GET", None),
    ("economic-calendar", "/economic-calendar?limit=5", "GET", None),
    ("jobs", "/jobs?limit=5", "GET", None),
]


def call(name, path, method, body):
    url = BASE + path
    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            code = resp.status
            has_data = False
            try:
                j = json.loads(raw)
                data = j.get("data") if isinstance(j, dict) else j
                if isinstance(data, dict):
                    has_data = any(
                        isinstance(v, (list, dict)) and len(v) > 0 for k, v in data.items() if k != "message"
                    ) or bool(data.get("items"))
                elif isinstance(data, list):
                    has_data = len(data) > 0
            except Exception:
                has_data = len(raw) > 50
            status = f"{code} {'✅data' if has_data else '⚠️empty'}"
    except urllib.error.HTTPError as e:
        status = f"{e.code} ❌HTTPError"
        with contextlib.suppress(Exception):
            detail = e.read().decode("utf-8", errors="replace")[:150]
            status += f" {detail}"
    except Exception as e:
        status = f"❌{type(e).__name__}: {str(e)[:120]}"
    print(f"{name:<32} {status}")


for name, path, method, body in ENDPOINTS:
    call(name, path, method, body)

