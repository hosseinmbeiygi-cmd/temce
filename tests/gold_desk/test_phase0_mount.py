"""Phase 0 mount guard — the personal GoldDesk router must actually mount.

`apps/api/router.py` wraps the personal GoldDesk include in try/except so a
broken optional surface never blocks startup. The cost of that safety valve is
that a missing mount turns every frontend call into a 404 while boot looks
healthy. This test pins the frontend-critical routes at the assembled-router
level, without starting a server or touching the DB.
"""

from __future__ import annotations

import pytest

# Routes the Phase 0 gold frontend actually calls (one representative method per
# surface). Analytics is public; the rest are auth-guarded at mount time, but
# path presence is what this test guards.
_REQUIRED_GOLD_PATHS = {
    "/gold/snapshot",
    "/gold/score",
    "/gold/history/score",
    "/gold/history/snapshot",
    "/gold/health",
    "/gold/freshness",
    "/gold/live-prices",
    "/gold/futures/health",
    "/gold/futures/positions",
    "/gold/kill-switch",
    "/gold/arbitrage",
    "/gold/coin-bubble",
    "/gold/etf-nav-premium",
    "/gold/portfolio",
    "/gold/portfolio/performance",
    "/gold/portfolio/dca",
    "/gold/portfolio/trades",
    "/gold/alerts/rules",
    "/gold/alerts/events",
    "/gold/dca/plan",
    "/gold/signals/recent",
    "/gold/tokens",
    "/gold/watchlist",
    "/gold/assistant-rules",
    "/gold/chat",
    "/gold/backtest",
    "/gold/backtest/strategy",
    "/gold/analytics/macro/calendar",
    "/gold/analytics/macro/live",
    "/gold/analytics/options/chain",
    "/gold/analytics/options/strategy",
    "/gold/analytics/risk/scenarios",
    "/gold/analytics/risk/stress",
    "/gold/ws",
}


def test_frontend_critical_gold_routes_are_mounted():
    from apps.api.router import Router

    mounted = {getattr(route, "path", "") for route in Router().setup().routes}

    missing = sorted(_REQUIRED_GOLD_PATHS - mounted)
    assert not missing, f"GoldDesk routes missing from the assembled router: {missing}"


def test_personal_router_is_not_mounted_twice_under_the_same_path_and_method():
    from apps.api.router import Router

    seen: set[tuple[str, frozenset[str]]] = set()
    duplicates: list[str] = []
    for route in Router().setup().routes:
        path = getattr(route, "path", "")
        if not path.startswith("/gold/"):
            continue
        methods = frozenset(getattr(route, "methods", None) or ())
        if not methods:
            continue
        key = (path, methods)
        if key in seen:
            duplicates.append(f"{sorted(methods)} {path}")
        seen.add(key)

    assert not duplicates, f"duplicate gold route registrations: {sorted(set(duplicates))}"
