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
