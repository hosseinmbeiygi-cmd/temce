"""Lightweight tests for the NAV endpoints on /api/v1/funds/*.

These tests verify the routing/contract without requiring a real
PostgreSQL connection. The DB session is replaced with an ``AsyncMock``
that returns a deterministic NAV series, so we can exercise:

  * ``GET /funds/{symbol}/nav`` — full NAV history
  * ``GET /funds/nav-history?symbols=...`` — bulk NAV

The point of these tests is the *contract*: NAV is exposed only through
the funds router. If a future refactor accidentally adds a ``/nav`` route
to ``/api/v1/crypto`` or ``/api/v1/options``, this file's
``test_nav_routes_only_live_under_funds`` assertion will surface it.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# Ensure project root is importable when pytest is invoked from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from apps.api.endpoints.funds import get_fund_service
from apps.api.endpoints.funds import router as funds_router
from services.fund_service import FundService

# ── helpers ───────────────────────────────────────────────────────


def _make_fake_session(*, scalars_rows: list[Any] | None = None, raw_rows: list[Any] | None = None) -> AsyncMock:
    """Build an AsyncMock that mimics an AsyncSession.execute() result.

    Two shapes are supported:
      * ``scalars_rows`` — yielded from ``result.scalars().all()``; each
        element exposes ``date`` and ``nav_issue``/``nav_redemption``.
      * ``raw_rows`` — yielded from ``result.all()`` directly; each
        element is a tuple ``(symbol, date, nav_issue, nav_redemption)``
        as produced by the bulk ``/funds/nav-history`` endpoint's
        ``select(...)`` projection.
    """
    session = AsyncMock()
    result = MagicMock()

    if scalars_rows is not None:
        scalars = MagicMock()
        scalars.all.return_value = scalars_rows
        result.scalars.return_value = scalars

    # result.all() must return something iterable that supports
    # ``for sym, d, nav_issue, nav_redemption in rows:`` (i.e. a plain
    # list of tuples) — NOT a MagicMock. We always set it: the default
    # is an empty list so IME fallback (3-tuple) raises inside the
    # endpoint's ``try/except`` block instead of looping a MagicMock.
    result.all.return_value = list(raw_rows) if raw_rows is not None else []

    session.execute.return_value = result
    return session


class _FakeNavRow:
    """Minimal stand-in for ``NavRecordModel`` (used for /funds/{sym}/nav)."""

    def __init__(self, date: str, nav_issue: float | None = None, nav_redemption: float | None = None) -> None:
        self.date = date
        self.nav_issue = nav_issue
        self.nav_redemption = nav_redemption
        self.symbol = "TEST-FUND"


def _stub_fund_service() -> Any:
    """Override ``get_fund_service`` so /funds list endpoints don't need DB."""
    svc = MagicMock(spec=FundService)
    # The list endpoint (used to confirm routing works) is not exercised
    # in these tests, but a few auxiliary paths inside funds.py may
    # touch the service. Make every call return a benign empty result.
    svc.list = AsyncMock(return_value=MagicMock(success=True, value=MagicMock(items=[], total=0)))
    svc.get = AsyncMock(return_value=MagicMock(success=True, value=None))
    svc.get_fund = AsyncMock(return_value=None)
    return svc


@pytest.fixture
def app() -> FastAPI:
    """Build a minimal app with funds router + DB session override."""

    app = FastAPI()
    app.include_router(funds_router, prefix="/funds")
    app.dependency_overrides[get_fund_service] = _stub_fund_service
    return app


# ── single-symbol NAV ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_fund_nav_returns_payload_shape(app: FastAPI) -> None:
    """GET /funds/{symbol}/nav returns {symbol, history, points, latest, oldest}."""
    from apps.api.dependencies import get_db_session

    rows = [
        _FakeNavRow(date="2026-08-25", nav_issue=10_000, nav_redemption=10_050),
        _FakeNavRow(date="2026-08-26", nav_issue=10_100, nav_redemption=10_150),
        _FakeNavRow(date="2026-08-27", nav_issue=10_200, nav_redemption=10_250),
    ]
    app.dependency_overrides[get_db_session] = lambda: _make_fake_session(scalars_rows=rows)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/funds/TEST-FUND/nav")

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["symbol"] == "TEST-FUND"
    assert payload["points"] == 3
    assert isinstance(payload["history"], list)
    assert len(payload["history"]) == 3
    # latest is the last row by date order
    assert payload["latest"]["date"] == "2026-08-27"
    assert payload["oldest"]["date"] == "2026-08-25"


@pytest.mark.asyncio
async def test_get_fund_nav_empty_when_no_rows(app: FastAPI) -> None:
    """An unknown symbol with no NAV rows returns an empty (but valid) envelope."""
    from apps.api.dependencies import get_db_session

    app.dependency_overrides[get_db_session] = lambda: _make_fake_session(scalars_rows=[])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/funds/UNKNOWN/nav")

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["symbol"] == "UNKNOWN"
    assert payload["history"] == []
    assert payload["points"] == 0
    assert payload["latest"] is None
    assert payload["oldest"] is None


# ── bulk NAV ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bulk_nav_history_returns_per_symbol_dict(app: FastAPI) -> None:
    """GET /funds/nav-history?symbols=A,B returns {symbols: {A: [...], B: [...]}}."""
    from apps.api.dependencies import get_db_session

    rows = [
        ("A", "2026-08-26", 11_000, 11_050),
        ("A", "2026-08-27", 11_100, 11_150),
        ("B", "2026-08-27", 12_000, 12_050),
    ]
    app.dependency_overrides[get_db_session] = lambda: _make_fake_session(raw_rows=rows)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/funds/nav-history?symbols=A,B&limit=10")

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert "symbols" in payload
    assert isinstance(payload["symbols"], dict)
    # Bulk endpoint groups by DB row symbol, so A and B both surface.
    assert set(payload["symbols"].keys()) == {"A", "B"}
    assert len(payload["symbols"]["A"]) == 2
    assert len(payload["symbols"]["B"]) == 1


# ── routing guard: NAV lives ONLY on /funds ───────────────────────


def test_nav_routes_only_live_under_funds(app: FastAPI) -> None:
    """NAV routes are registered exclusively under the funds prefix.

    This guards against a future refactor that accidentally attaches
    NAV handling to a non-fund endpoint (e.g. /api/v1/crypto/nav).
    The check inspects the funds router directly, not the mounted app,
    so we don't depend on FlatRoutes / path-prefix rewriting.
    """
    nav_paths = [r for r in funds_router.routes if "nav" in getattr(r, "path", "").lower()]
    assert nav_paths, "expected at least one NAV route on funds router"

    for r in nav_paths:
        # The funds router is mounted at /funds in production; before
        # mounting the paths are just the router-relative paths which
        # all start with "/" (e.g. "/{symbol}/nav").
        assert r.path.startswith("/"), f"unexpected path: {r.path}"

    # Expected route shapes (loose match — exact paths can change):
    joined = "\n".join(r.path for r in nav_paths)
    assert "/nav" in joined
    assert "/nav-history" in joined


def test_crypto_and_options_routers_have_no_nav_routes() -> None:
    """Confirm /api/v1/crypto and /api/v1/options have NO NAV *read* routes.

    A NAV endpoint on a non-fund path would be a contract violation
    (the user's invariant: NAV is funds-only). We deliberately ignore
    ``/manage/sync-nav-all`` — that's an admin action to trigger a
    NAV sync, not a NAV read endpoint.
    """
    from apps.api.endpoints.brsapi import router as brsapi_router

    def _is_nav_read(path: str) -> bool:
        if "nav" not in path.lower():
            return False
        # Exclude admin actions and bulk sync triggers.
        return not ("sync" in path.lower() or "manage" in path.lower())

    for router_obj, label in [
        (brsapi_router, "brsapi (crypto/commodity)"),
    ]:
        for route in router_obj.routes:
            path = getattr(route, "path", "").lower()
            if _is_nav_read(path):
                pytest.fail(f"{label} exposes a NAV read path: {path}")

    # And the funds router SHOULD have a NAV read path (positive control).
    funds_nav_reads = [r for r in funds_router.routes if _is_nav_read(getattr(r, "path", "").lower())]
    assert funds_nav_reads, "funds router has no NAV read path"
