"""Contract tests for ``POST /brsapi/manage/sync-nav-all``.

The endpoint used to iterate a hardcoded ``BRSAPI_ETF_SYMBOLS`` list and
call ``sync_nav`` per symbol itself. It now delegates to
``BrsApiSyncService.sync_nav_all`` so fund discovery (sector-aware,
insurance/pension excluded), deduplication, and the "already has today's
NAV" fast path all live in one place.

These tests lock in that delegation *and* the response contract, without a
database or network: the session and the BrsApi client are mocked.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# Ensure project root is importable when pytest is invoked from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from apps.api.dependencies import get_db_session
from apps.api.endpoints.brsapi import router as brsapi_router
from brsapi.services.sync_service import SyncReport


def _make_app(fake_session: object) -> FastAPI:
    app = FastAPI()
    app.include_router(brsapi_router, prefix="/brsapi")
    app.dependency_overrides[get_db_session] = lambda: fake_session
    return app


def _report(**overrides: object) -> SyncReport:
    defaults: dict[str, object] = {
        "endpoint": "/Tsetmc/Nav.php",
        "success": True,
        "items_count": 7,
        "duration_ms": 123.4,
        "error": None,
        "skipped": False,
        "failed_symbols": [],
        "skipped_symbols": [],
        "no_data_symbols": [],
        "normalized_symbols": [],
    }
    defaults.update(overrides)
    return SyncReport(**defaults)  # type: ignore[arg-type]


def _patch_service(return_value: SyncReport) -> tuple[MagicMock, MagicMock]:
    """Patch ``BrsApiSyncService`` with a fake class + instance.

    Returns ``(fake_cls, fake_instance)`` so callers can assert on the
    instance methods that the endpoint should (or should not) use.
    """
    fake_cls = MagicMock()
    fake_svc = MagicMock()
    fake_svc.sync_nav_all = AsyncMock(return_value=return_value)
    fake_cls.return_value = fake_svc
    return fake_cls, fake_svc


@pytest.mark.asyncio
async def test_delegates_to_service_sync_nav_all() -> None:
    """The endpoint calls ``sync_nav_all`` once and never loops symbols itself."""
    fake_session = MagicMock()
    report = _report()
    fake_cls, fake_svc = _patch_service(report)

    with (
        patch("apps.api.endpoints.brsapi.get_client", AsyncMock(return_value=MagicMock())),
        patch("brsapi.services.sync_service.BrsApiSyncService", fake_cls),
    ):
        app = _make_app(fake_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/brsapi/manage/sync-nav-all")

    assert resp.status_code == 200, resp.text

    # Delegation happened exactly once, with the request session.
    assert fake_svc.sync_nav_all.await_count == 1
    args, kwargs = fake_svc.sync_nav_all.call_args
    assert args[0] is fake_session
    assert kwargs == {"max_symbols": 0}

    # The endpoint must not do its own per-symbol loop.
    fake_svc.sync_nav.assert_not_called()
    fake_svc._get_fund_symbols.assert_not_called()


@pytest.mark.asyncio
async def test_response_serializes_sync_report_fields() -> None:
    """The response body exposes the ``SyncReport`` dataclass fields."""
    fake_session = MagicMock()
    report = _report(success=False, items_count=3, error="2 symbols failed", failed_symbols=["بیدار", "آگاس"])
    fake_cls, _ = _patch_service(report)

    with (
        patch("apps.api.endpoints.brsapi.get_client", AsyncMock(return_value=MagicMock())),
        patch("brsapi.services.sync_service.BrsApiSyncService", fake_cls),
    ):
        app = _make_app(fake_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/brsapi/manage/sync-nav-all")

    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Top-level success mirrors report.success (no longer hardcoded True).
    assert report.success is False
    assert body["success"] is False

    data = body["data"]
    assert set(data) == {
        "endpoint",
        "success",
        "items_count",
        "duration_ms",
        "error",
        "skipped",
        "failed_symbols",
        "skipped_symbols",
        "no_data_symbols",
        "normalized_symbols",
    }
    assert data["endpoint"] == "/Tsetmc/Nav.php"
    assert data["items_count"] == 3
    assert data["error"] == "2 symbols failed"
    assert data["failed_symbols"] == ["بیدار", "آگاس"]
    assert data["skipped_symbols"] == []
    assert data["no_data_symbols"] == []
    assert data["normalized_symbols"] == []


@pytest.mark.asyncio
async def test_response_exposes_normalized_symbols() -> None:
    """Duplicate-name twins folded onto a base symbol are reported, not hidden."""
    fake_session = MagicMock()
    report = _report(normalized_symbols=["ابتکار2", "آتیه ملت4"])
    fake_cls, _ = _patch_service(report)

    with (
        patch("apps.api.endpoints.brsapi.get_client", AsyncMock(return_value=MagicMock())),
        patch("brsapi.services.sync_service.BrsApiSyncService", fake_cls),
    ):
        app = _make_app(fake_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/brsapi/manage/sync-nav-all")

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["normalized_symbols"] == ["ابتکار2", "آتیه ملت4"]


@pytest.mark.asyncio
async def test_max_symbols_query_param_is_forwarded() -> None:
    """``?max_symbols=5`` reaches the service so the per-run cap is honoured."""
    fake_session = MagicMock()
    fake_cls, fake_svc = _patch_service(_report())

    with (
        patch("apps.api.endpoints.brsapi.get_client", AsyncMock(return_value=MagicMock())),
        patch("brsapi.services.sync_service.BrsApiSyncService", fake_cls),
    ):
        app = _make_app(fake_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/brsapi/manage/sync-nav-all?max_symbols=5")

    assert resp.status_code == 200, resp.text
    assert fake_svc.sync_nav_all.call_args.kwargs == {"max_symbols": 5}
