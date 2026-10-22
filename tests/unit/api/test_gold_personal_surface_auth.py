"""The `/gold` personal surface must not answer anonymous callers.

Background
----------
``src/gold_desk/api.py`` declared "prefix: /gold (بدون auth چون شخصی است)" and
was mounted with no auth dependency at all, so 62 operations — portfolio
holdings and trades, tax export, alert rules, API tokens, watchlist, DCA plans,
chat — answered anyone who could reach the API. That is somebody's own money and
position data.

The mount now carries ``_require_user``, the same gate every other personal mount
uses. Exactly three routes stay anonymous on purpose, on ``anonymous_router`` in
that module:

  * ``/gold/health``          — container/K8s liveness probe (a probe holds no JWT)
  * ``/gold/assistant-rules`` — the spec card the *pre-login* ``/markets/gold``
                                and ``/markets/silver`` pages render
  * ``/gold/ws``              — a socket; it verifies its own token in the handler

This test locks in both halves, so a later edit cannot silently reopen the
surface nor close the two routes the probe and the public pages depend on.

STEP 7D-1 adds the same lock for ``/gold/analytics``, which is mixed: platform-
derived analytics behind JWT, stateless calculators and the live price summary
anonymous. The classes are decided by *what the response contains* — see the
policy comment in ``apps/api/endpoints/gold_analytics.py`` and the exemption list
in ``scripts/check_router_auth.py``.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

PERSONAL_ROUTES: list[tuple[str, str]] = [
    ("GET", "/api/v1/gold/snapshot"),
    ("GET", "/api/v1/gold/score"),
    ("GET", "/api/v1/gold/portfolio"),
    ("GET", "/api/v1/gold/portfolio/trades"),
    ("GET", "/api/v1/gold/portfolio/tax"),
    ("GET", "/api/v1/gold/alerts/rules"),
    ("GET", "/api/v1/gold/watchlist"),
    ("GET", "/api/v1/gold/tokens"),
    ("GET", "/api/v1/gold/metrics"),
    ("POST", "/api/v1/gold/chat"),
    # Gold calculator/futures router (apps/api/endpoints/gold.py). Futures
    # positions are personal money, so the whole mount is user-gated; these
    # cases also prove the router is actually mounted (404 would fail here).
    ("GET", "/api/v1/gold/live-prices"),
    ("GET", "/api/v1/gold/etf-nav-premium"),
    ("GET", "/api/v1/gold/futures/positions"),
    ("GET", "/api/v1/gold/kill-switch"),
]


@pytest.mark.parametrize(("method", "url"), PERSONAL_ROUTES)
async def test_personal_routes_reject_anonymous_callers(
    client: AsyncClient, method: str, url: str
) -> None:
    response = await client.request(method, url, json={} if method == "POST" else None)

    assert response.status_code == 401, f"{method} {url} -> {response.status_code} {response.text}"


async def test_health_probe_stays_anonymous(client: AsyncClient) -> None:
    """The Docker HEALTHCHECK hits this with no credentials (see Dockerfile.golddesk)."""
    response = await client.get("/api/v1/gold/health")

    # 200 healthy / 503 degraded — both are "the route answered", never a 401.
    assert response.status_code in {200, 503}, response.text


async def test_assistant_rules_stay_anonymous(client: AsyncClient) -> None:
    """Rendered by /markets/gold and /markets/silver, which load before login."""
    response = await client.get("/api/v1/gold/assistant-rules")

    assert response.status_code == 200, response.text


async def test_personal_routes_pass_auth_for_a_real_user(user_client: AsyncClient) -> None:
    """Guard against "closed" being implemented as "broken for everyone"."""
    response = await user_client.get("/api/v1/gold/snapshot")

    assert response.status_code not in {401, 403}, response.text


def test_websocket_stream_refuses_a_tokenless_handshake(app) -> None:
    """The socket streams the same snapshot, so it needs the same gate.

    A browser cannot attach headers to a WebSocket handshake, so the route
    verifies a ``token`` query parameter itself (the shared helper
    ``apps.api.endpoints.websocket.verify_websocket_token``) and closes the
    connection with 1008 before accepting. The route lives on the anonymous
    router because the HTTP auth dependency would reject the handshake before
    that check ever ran.
    """
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    with (
        TestClient(app) as test_client,
        pytest.raises(WebSocketDisconnect) as denied,
        test_client.websocket_connect("/api/v1/gold/ws"),
    ):
        pass

    assert denied.value.code == 1008


# ── STEP 7D-1: /gold/analytics split ─────────────────────────────────────

#: Platform-derived analytics, plus every write on the mount. The POSTs are
#: listed here even where the handler is a pure calculator because
#: ``SecurityMiddleware`` requires a bearer token for any write under
#: ``/api/v1/gold/`` — the router must agree with what the app actually enforces.
ANALYTICS_SIGNAL_ROUTES: list[tuple[str, str]] = [
    ("GET", "/api/v1/gold/analytics/coins"),
    ("GET", "/api/v1/gold/analytics/arbitrage"),
    ("GET", "/api/v1/gold/analytics/aed-history"),
    ("GET", "/api/v1/gold/analytics/options/chain"),
    ("GET", "/api/v1/gold/analytics/macro/live"),
    ("GET", "/api/v1/gold/analytics/risk/scenarios"),
    ("POST", "/api/v1/gold/analytics/risk/stress"),
    ("POST", "/api/v1/gold/analytics/macro/posture"),
    ("POST", "/api/v1/gold/analytics/macro/aed-parity"),
    ("POST", "/api/v1/gold/analytics/macro/iran-events"),
    ("POST", "/api/v1/gold/analytics/physical/coin-bubbles"),
    ("POST", "/api/v1/gold/analytics/physical/ime-arbitrage"),
    ("POST", "/api/v1/gold/analytics/physical/mesghal"),
    ("POST", "/api/v1/gold/analytics/physical/assay"),
    ("POST", "/api/v1/gold/analytics/options/black76"),
    ("POST", "/api/v1/gold/analytics/options/implied-volatility"),
    ("POST", "/api/v1/gold/analytics/options/pcr"),
    ("POST", "/api/v1/gold/analytics/options/max-pain"),
    ("POST", "/api/v1/gold/analytics/options/enrich"),
    ("POST", "/api/v1/gold/analytics/options/strategy"),
    ("POST", "/api/v1/gold/analytics/options/margin"),
    ("POST", "/api/v1/gold/analytics/futures/term-structure"),
]

#: Reference/price reads with no platform-derived signal — the contract their
#: own HTTP tests already assert.
ANALYTICS_PUBLIC_ROUTES: list[tuple[str, str]] = [
    ("GET", "/api/v1/gold/analytics/summary"),
    ("GET", "/api/v1/gold/analytics/macro/calendar"),
    ("GET", "/api/v1/gold/analytics/macro/iran-events"),
    ("GET", "/api/v1/gold/analytics/feed-health"),
]


@pytest.mark.parametrize(("method", "url"), ANALYTICS_SIGNAL_ROUTES)
async def test_analytics_signal_routes_reject_anonymous_callers(
    client: AsyncClient, method: str, url: str
) -> None:
    response = await client.request(method, url, json={} if method == "POST" else None)

    assert response.status_code == 401, f"{method} {url} -> {response.status_code}"


@pytest.mark.parametrize(("method", "url"), ANALYTICS_PUBLIC_ROUTES)
async def test_analytics_public_routes_stay_anonymous(
    client: AsyncClient, method: str, url: str
) -> None:
    """``GET /gold/analytics/summary`` feeds the pre-login gold/silver pages.

    A price read may legitimately fail downstream (503 when no feed answers),
    but it must never answer *anonymous* callers with an auth wall.
    """
    response = await client.request(method, url, json={} if method == "POST" else None)

    assert response.status_code not in {401, 403}, (
        f"{method} {url} -> {response.status_code} {response.text}"
    )


def test_analytics_route_split_is_exhaustive() -> None:
    """Every operation on the mount is classified exactly once."""
    from apps.api.endpoints.gold_analytics import router

    declared = {
        (sorted(route.methods - {"HEAD"})[0], f"/api/v1/gold/analytics{route.path}")
        for route in router.routes
    }
    classified = {(m, u) for m, u in ANALYTICS_SIGNAL_ROUTES} | {
        (m, u) for m, u in ANALYTICS_PUBLIC_ROUTES
    }

    assert declared == classified, (
        f"uncategorised: {sorted(declared - classified)} / "
        f"unknown: {sorted(classified - declared)}"
    )


async def test_analytics_signal_route_works_for_a_real_user(user_client: AsyncClient) -> None:
    """JWT-gating must not mean "broken for authenticated callers"."""
    response = await user_client.get("/api/v1/gold/analytics/risk/scenarios")

    assert response.status_code not in {401, 403}, response.text
